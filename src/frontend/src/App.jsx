import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
// 【注意】本地安装依赖后取消注释: npm install remark-gfm remark-math rehype-katex katex
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

import { FileText, CheckCircle, Edit3, Play, Loader, Clock, Terminal, Search, BookOpen, Upload } from 'lucide-react';

export default function App() {
  const [goal, setGoal] = useState("调研时空网格编码技术");
  const [threadId, setThreadId] = useState("thread_" + Date.now());
  const [status, setStatus] = useState("idle"); 
  const [logs, setLogs] = useState([]);
  const [plan, setPlan] = useState(null);
  const [report, setReport] = useState("");
  const [feedback, setFeedback] = useState("");
  const [tasks, setTasks] = useState({});
  
  // 上传相关状态
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);
  
  const eventSourceRef = useRef(null);
  const logsEndRef = useRef(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const addLog = (message) => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), message }]);
  };

  const startResearch = async () => {
    setStatus("running");
    setLogs([]);
    setReport("");
    setPlan(null);
    setTasks({}); 
    const newThreadId = "thread_" + Date.now();
    setThreadId(newThreadId);
    // 端口保持您设置的 8002
    const url = `http://localhost:8002/api/research/stream/${newThreadId}?goal=${encodeURIComponent(goal)}`;
    connectSSE(url);
  };

  const connectSSE = (url, isResume = false) => {
    if (eventSourceRef.current) eventSourceRef.current.close();
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
        if (!isResume) addLog("连接成功，准备开始...");
    };

    es.addEventListener("log", (event) => {
      const data = JSON.parse(event.data);
      addLog(data.message);
    });

    es.addEventListener("progress", (event) => {
      const data = JSON.parse(event.data);
      setTasks(prev => ({
        ...prev,
        [data.task_id]: { ...prev[data.task_id], ...data }
      }));
      if (data.message) {
        addLog(data.message);
      }
    });

    es.addEventListener("interrupt", (event) => {
      const data = JSON.parse(event.data);
      setPlan(data.data);
      setStatus("waiting_review");
      // 此时流可以关闭，等待用户操作
      es.close();
    });

    es.addEventListener("report_token", (event) => {
      const data = JSON.parse(event.data);
      setReport(prev => prev + data.token);
    });

    es.addEventListener("done", (event) => {
      setStatus("completed");
      addLog("✅ 任务全部完成！");
      es.close();
    });

    // 【新增】监听后端明确发送的错误事件
    es.addEventListener("error", (event) => {
        // 这是自定义的 error 事件类型，不是 SSE 协议的 onerror
        const data = JSON.parse(event.data);
        console.error("Backend Error:", data);
        addLog(`❌ 后端错误: ${data.error}`);
        es.close();
        setStatus("idle");
    });

    // 原生 onerror 处理连接断开
    es.onerror = (err) => {
      if (es.readyState === EventSource.CLOSED) return;
      console.error("SSE Connection Error:", err);
      es.close();
      if (status !== "completed" && status !== "waiting_review") {
        addLog("⚠️ 连接异常断开 (请检查后端控制台)");
        setStatus("idle");
      }
    };
  };

  // --- 上传相关逻辑 ---
  const handleFileSelect = () => {
    fileInputRef.current.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    addLog(`📤 开始上传文件: ${file.name}`);

    const formData = new FormData();
    formData.append("file", file);

    try {
      // 端口保持 8002
      const response = await fetch("http://localhost:8002/api/ingest/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        lines.forEach(line => {
          if (line.startsWith("event: ")) {
            const match = line.match(/event: (.*)\n/);
            if (!match) return;
            const eventType = match[1];
            const dataMatch = line.match(/data: (.*)/);
            if (!dataMatch) return;
            const dataContent = dataMatch[1];
            const d = JSON.parse(dataContent);

            // 复用 addLog 将解析日志显示在主日志窗口
            if (eventType === "log") {
                addLog(d.message);
            } else if (eventType === "error") {
                addLog(`❌ 解析错误: ${d.error}`);
            }
          }
        });
      }
      addLog(`✅ 文件 ${file.name} 处理流程结束`);
    } catch (e) {
      console.error(e);
      addLog(`❌ 上传/解析失败: ${e.message}`);
    } finally {
      setIsUploading(false);
      // 清空 input 防止重复上传同个文件不触发 change
      e.target.value = ""; 
    }
  };

  const handleApprove = async () => {
    setStatus("running");
    setPlan(null); 
    await fetchAndStream("approve");
  };

  const handleRevise = async () => {
    if (!feedback.trim()) return alert("请输入修改意见");
    setStatus("running");
    setPlan(null);
    await fetchAndStream("revise", feedback);
  };

  const fetchAndStream = async (action, fb = null) => {
    try {
      const response = await fetch("http://localhost:8002/api/research/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, action, feedback: fb }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); 

        lines.forEach(line => {
          if (line.startsWith("event: ")) {
            const match = line.match(/event: (.*)\n/);
            if (!match) return;
            const eventType = match[1];
            const dataMatch = line.match(/data: (.*)/);
            if (!dataMatch) return;
            const dataContent = dataMatch[1];
            
            if (eventType === "log") {
               const d = JSON.parse(dataContent);
               addLog(d.message);
            } else if (eventType === "progress") {
              const d = JSON.parse(dataContent);
              setTasks(prev => ({ ...prev, [d.task_id]: { ...prev[d.task_id], ...d } }));
              if (d.message) addLog(d.message);
            } else if (eventType === "report_token") {
              const d = JSON.parse(dataContent);
              setReport(prev => prev + d.token);
            } else if (eventType === "done") {
              setStatus("completed");
              addLog("✅ 任务全部完成！");
            } else if (eventType === "interrupt") {
               const d = JSON.parse(dataContent);
               setPlan(d.data);
               setStatus("waiting_review");
            } else if (eventType === "error") {
               const d = JSON.parse(dataContent);
               addLog(`❌ 后端错误: ${d.error}`);
            }
          }
        });
      }
    } catch (e) {
      console.error(e);
      addLog("❌ 恢复执行失败");
      setStatus("idle");
    }
  };

  const getCleanReport = (text) => {
    if (!text) return "";
    let clean = text.replace(/^```(markdown)?\s*/i, "");
    clean = clean.replace(/```\s*$/, "");
    return clean;
  };

  const sortedTasks = Object.values(tasks).sort((a, b) => (a.task_id || 0) - (b.task_id || 0));

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-8 font-sans text-gray-800">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 text-center">
          <h1 className="text-3xl md:text-4xl font-bold text-blue-600 flex items-center justify-center gap-3">
            <FileText className="w-10 h-10" /> DeepResearch Agent
          </h1>
          <p className="text-gray-500 mt-2 text-lg">基于 LangGraph 的人机协同研究助手</p>
        </header>

        <div className="bg-white p-6 rounded-xl shadow-sm mb-6 border border-gray-100">
          <div className="flex flex-col md:flex-row gap-4">
            {/* 上传文件部分 */}
            <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
                className="hidden" 
                accept=".pdf,.docx" 
            />
            <button
              onClick={handleFileSelect}
              disabled={status === "running" || isUploading}
              className="bg-gray-100 text-gray-700 px-4 py-4 rounded-xl hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-300 border border-gray-200 flex items-center justify-center gap-2 transition-all whitespace-nowrap"
              title="上传本地文档进行解析"
            >
              {isUploading ? <Loader className="animate-spin w-5 h-5" /> : <Upload className="w-5 h-5" />}
              上传文档
            </button>

            <div className="flex-1 relative">
                <input
                type="text"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                className="w-full px-5 py-4 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg shadow-sm"
                placeholder="输入您的研究目标..."
                disabled={status === "running"}
                onKeyDown={(e) => e.key === 'Enter' && !status.match(/running|waiting/) && startResearch()}
                />
            </div>
            <button
              onClick={startResearch}
              disabled={status === "running" || status === "waiting_review"}
              className="bg-blue-600 text-white px-8 py-4 rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-bold text-lg whitespace-nowrap"
            >
              {status === "running" ? <Loader className="animate-spin w-6 h-6" /> : <Play className="w-6 h-6" />}
              {status === "running" ? "研究中..." : "开始研究"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
          {/* 左侧：日志区 */}
          <div className="lg:col-span-3 flex flex-col h-[600px]">
             <div className="bg-gray-900 text-green-400 p-4 rounded-xl shadow-md flex-1 overflow-hidden border border-gray-800 flex flex-col font-mono text-sm">
              <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-4 flex items-center gap-2 border-b border-gray-700 pb-2">
                <Terminal size={14} /> 执行日志
              </h2>
              <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
                {logs.length === 0 && <div className="text-gray-600 italic text-center mt-10">...</div>}
                {logs.map((log, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-gray-500 text-xs min-w-[50px]">{log.time}</span>
                    <span className={`
                        ${log.message.includes("✅") ? "text-green-300 font-bold" : ""}
                        ${log.message.includes("❌") ? "text-red-400" : ""}
                        ${log.message.includes("上传") || log.message.includes("解析") ? "text-purple-300" : "text-gray-300"}
                        ${log.message.includes("不足") ? "text-yellow-300" : ""}
                    `}>
                        {log.message}
                    </span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
          
          {/* 中间：任务进度 */}
          <div className="lg:col-span-4 flex flex-col h-[600px]">
            <div className="bg-white p-4 rounded-xl shadow-md flex-1 overflow-y-auto border border-gray-100 flex flex-col">
              <h2 className="text-sm font-bold text-gray-500 uppercase tracking-widest mb-4 flex items-center gap-2 border-b pb-2 sticky top-0 bg-white z-10">
                <Search size={16} /> 实时研究进展
              </h2>
              <div className="space-y-4">
                {sortedTasks.length === 0 && (
                  <div className="text-gray-400 text-center mt-20 text-sm">暂无任务，请开始研究...</div>
                )}
                {sortedTasks.map((task) => (
                  <div key={task.task_id} className={`p-4 rounded-lg border transition-all ${task.status === 'completed' ? 'border-green-200 bg-green-50' : 'border-blue-200 bg-blue-50'}`}>
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-bold text-gray-800 text-sm flex items-center gap-2">
                        <span className="bg-white border border-gray-200 text-gray-600 text-xs px-1.5 py-0.5 rounded">#{task.task_id}</span>
                        {task.title}
                      </h4>
                      {task.status === 'researching' ? (
                        <Loader size={14} className="animate-spin text-blue-500" />
                      ) : (
                        <CheckCircle size={14} className="text-green-500" />
                      )}
                    </div>
                    
                    {task.status === 'researching' && (
                      <p className="text-xs text-blue-600 animate-pulse">🔍 {task.message.replace("正在研究", "").replace("任务...", "")} (检索中...)</p>
                    )}
                    
                    {task.status === 'completed' && (
                      <div className="mt-2 text-xs text-gray-600 bg-white p-2 rounded border border-green-100">
                        <strong className="block text-green-700 mb-1">💡 研究结论:</strong>
                        {task.summary}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 右侧：最终报告 */}
          <div className="lg:col-span-5 flex flex-col h-[600px]">
            <div className="bg-white p-6 rounded-xl shadow-md flex-1 overflow-y-auto border border-gray-100 relative">
              <h2 className="text-sm font-bold text-gray-500 uppercase tracking-widest mb-4 flex items-center gap-2 border-b pb-2 sticky top-0 bg-white z-10">
                <BookOpen size={16} /> 最终报告
                {status === "running" && report && <span className="text-xs normal-case font-normal bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full ml-2 animate-pulse">Writing...</span>}
              </h2>
              
              {report ? (
                <div className="markdown-content max-w-none break-words text-sm">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {getCleanReport(report)}
                  </ReactMarkdown>
                  {status === "running" && <span className="inline-block w-1.5 h-3 bg-blue-500 ml-1 animate-pulse align-middle"></span>}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-300 space-y-4">
                  <FileText size={48} className="opacity-20" />
                  <p className="text-sm">最终报告将在此处生成</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 模态框：人工审核计划 */}
        {status === "waiting_review" && plan && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden border border-gray-200">
              <div className="p-6 border-b bg-gray-50 flex justify-between items-center">
                <div>
                    <h3 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                        <CheckCircle className="text-blue-600" /> 审核研究大纲
                    </h3>
                    <p className="text-gray-500 text-sm mt-1">AI 已规划 {plan.length} 个子任务，请确认是否执行。</p>
                </div>
                <div className="text-xs bg-yellow-100 text-yellow-800 px-3 py-1 rounded-full font-medium">
                    需人工确认
                </div>
              </div>
              
              <div className="p-6 overflow-y-auto flex-1 space-y-4 bg-white">
                {plan.map((task) => (
                  <div key={task.id} className="group bg-white p-5 rounded-xl border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-bold text-blue-600 text-lg flex items-center gap-2">
                        <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded">Task {task.id}</span>
                        {task.title}
                      </h4>
                    </div>
                    <div className="space-y-1 pl-1">
                        <p className="text-sm text-gray-700"><strong className="text-gray-900">目标:</strong> {task.intent}</p>
                        <p className="text-sm text-gray-500 flex items-center gap-1">
                            <Clock size={12} /> 
                            Query: {task.query}
                        </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-6 border-t bg-gray-50 space-y-4">
                <div className="flex gap-3">
                  <input
                    type="text"
                    placeholder="如果大纲不准确，请在此输入修改建议..."
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none shadow-sm"
                  />
                </div>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={handleRevise}
                    className="px-6 py-2.5 text-gray-700 bg-white border border-gray-300 hover:bg-gray-100 rounded-xl font-medium flex items-center gap-2 transition-colors shadow-sm"
                  >
                    <Edit3 size={18} />
                    提出修改
                  </button>
                  <button
                    onClick={handleApprove}
                    className="px-8 py-2.5 text-white bg-blue-600 hover:bg-blue-700 rounded-xl font-bold flex items-center gap-2 shadow-md transition-all active:scale-95"
                  >
                    <CheckCircle size={18} />
                    批准并执行
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
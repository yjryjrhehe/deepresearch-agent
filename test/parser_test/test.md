第 46 卷 第 1 期 2021 年 1 月

DOI ： 10.13203/j.whugis20200234

Vol.46 No.1 Jan. 2021

文章编号 ： 1671⁃8860(2021)01⁃0050⁃08

这是一张包含一个二维码的图片。二维码是黑色模块排列在正方形网格上的图案，用于存储信息。扫描该二维码可以获取其中包含的信息，如网址、文本或联系方式。

<!-- image -->

# 空天网格化星间通视及路由路径规划算法

李 爽 1 李德仁 2 程承旗 3 陈 波 3 沈 欣 2 童晓冲 4

1 复旦大学历史地理研究中心， 上海， 200433

2 武汉大学测绘遥感信息工程国家重点实验室， 湖北 武汉， 430079

3 北京大学工学院， 北京， 100871

4 信息工程大学地理空间信息学院， 河南 郑州， 450001

摘 要 ： 通信、 导航、 遥感一体的天基信息服务系统的建设将对跨境实时通信、 动目标全球跟踪、 灾害快速响应 等提供有力保障， 同时也对高效的网络通信 , 特别是卫星路由规划算法提出了新的要求。为优化通信链路， 进 一步降低时延， 充分利用网格空间关系直视、 编码计算效率高的优势， 提出了卫星星座空间互联网格化计算方 法。基于 GeoSOT⁃3D （ geographic coordinate subdivision grid with one dimension integer coding on 2 n Tree ⁃3D ） 模型， 构建了空天网格索引大表， 并提出了一套通过查询网格通视情况来进行卫星通视分析以及星间路由规 划的算法。通过仿真 90/15/2 的 Walker 星座， 构建空天网格索引大表， 进行星间通视分析、 星间效率规划的实 验验证与效率对比， 结果发现， 网格通视分析效率较传统算法提升 2.2 倍； 基于预先建立通视大表的通视分析 效率较传统算法提升 20.9 倍； 网格化星间路由规划效率在最短距离约束下提升近 25 倍； 在最小跳数约束下则 提升约 20 倍。因此， 该算法具有可行性与高效性， 能显著提升星间通视及空间链路规划的计算效率。此外， 该算法能够用于紧急通信、 灾害预警、 海上救援等方面， 为卫星互联网建设作出贡献。

关键词 ： 空天信息网格； 空天全域网格索引大表； 星间通视分析； 卫星路由路径规划

中图分类号 ： P208

文献标志码： A

目前， 中国对导航、 遥感等天基信息的覆盖 范围需求已从国内拓展到全球， 在 '一星多用、 多 星组网' 的应用需求以及紧急通信、 灾害预警、 海 上救援等场景的需求下， 面对无法在全球范围建 设地面站这一现实难题， 卫星间的高效通信具有 非常重要的研究意义［ 1 -4 ］ 。与此同时， 文献［ 5 -6 ］ 提出构建与地面网络深度耦合的集成化的天基 信息实时服务系统， 即同时提供定位、 导航、 授时、 遥感、通信服务（ positioning ， navigation ， timing ， remote sensing ， communication ， PNTRC ）系统， 该 系统具有上百颗卫星的卫星星座， 可实现与地面 互联网的互联互通。

在大规模的低轨通信、 遥感星座的运控过程 中， 可见性分析是实现全球范围遥感信息的快速 回传， 特别是境外目标观测数据的快速回传的重 要基础。现有通视分析方法在计算卫星之间、 卫 星与地面观测点的相对位置时， 需要实时构建卫 星相对坐标系、 地心地平坐标系， 并采用浮点数

收稿日期 ： 2020⁃05⁃17

项目资助 ： 国家重点研发计划（ 2018YFB0505300 ）； 复旦大学引进人才科研启动费（ JIH3142004 ）。

第一作者： 李爽， 博士， 副研究员， 主要从事网格时空模型及历史 GIS 工作。 li\_shuang@fudan.edu.cn

通讯作者 ： 程承旗， 博士， 教授。 ccq@pku.edu.cn

在不同卫星轨道、 甚至不同星座间进行计算， 算 法复杂度高［ 7 -8 ］ 。境外数据获取涉及大量路由传 输规划， 文献［ 9 -10 ］对卫星通信网络路由及卫星 网络拓扑结构进行了研究， 主要针对通信卫星星 座， 包括有集中式路由、 分布式路由等结构。考 虑到研发成本低、 覆盖范围广、 重返周期短等优 势， 不构建星间链路的低轨互联网卫星星座成为 近年来对地实时观测与通信的新方向。然而传 统的路由规划方法是基于星间链路构建的，在 Starlink 、 OneWeb 以及鸿雁、 鸿云、 PNTRC 等大 星座组网（至少包含数百颗、 甚至有规划上千颗） 应用场景中， 传统的几何方法难以应对大规模、 复杂网络环境下应急任务的快速调度， 以及其对 星间可见性分析的快速、 高精度要求， 因此需要 进一步结合低轨高时变卫星大星座的特点， 研究 更高效的通视计算、 路由规划方法。

空间网格数据模型及其索引方法具有划分 方式简单、 空间计算高效的特点［ 11 ］ 。其中， 基于

2 n 及整型一维数组全球经纬度剖分网格（ geo⁃ graphic coordinate subdivision grid with one dimen⁃ sion integer coding on 2 n Tree ， GeoSOT ）是二三 维一体的、 多层次嵌套的、 等经纬度划分的统一 位置框架， 具有网格空间关系直视、 编码计算效 率高的优势， 可用来进行空间位置的标识、 表达、 计算， 文献［ 12 -14 ］发现 GeoSOT -3D 立体网格对 提升空间计算效率有显著帮助。因此， 本文将 GeoSOT -3D 立体网格拓展至航空航天范围， 开 展星间互联计算的探讨， 旨在通过构建空天全域 网格索引大表， '以空间换时间' ， 将复杂的星间 通视计算转为卫星所在网格的固有属性查询， 提 升通视计算、 空间链路规划的效率， 进而探讨遥 感信息快速回传的有效途径， 发展更高效的通视 计算、 星间路由规划的计算方法。

# 1 卫星网格化建模

空天网格体系与空天网格索引大表是网格 化卫星星座快速互联计算的重要基础。其核心 思路是将 GeoSOT 框架体系扩展至空天范围， 对 所有空天范围的立体空间区块进行标识， 形成空 天网格索引大表。在此基础上， 对卫星轨迹、 资 源实现网格化， 也为后续的快速互联计算提供 途径。

## 1.1 空天网格体系

本文引入 GeoSOT -3D 模型， 并将其应用至 航空航天范围， 即把空天划分成连续的立体空间 区块， 每个区块都给与了一个可以计算的整型编 码， 由此形成的坐标系称为空天网格坐标体系， 在经纬度坐标体系基础上增加一种离散网格坐 标， 对现实空间进行标识、 表达与计算。

## 1.2 空天全域网格索引大表

本文利用网格数据模型与索引技术， 建立了 跨领域、 多尺度、 无缝无叠、 覆盖全球的多源数据 编码检索模型。以网格索引大表为依托， 通过简 便快捷的编码处理， 提供空间数据的索引技术， 实现对多源异构空间数据的快速汇集与综合管 理。其中， 卫星作为重要的空间对象， 其相应时 空轨迹将被离散化并存于空天全域网格索引大 表中。索引大表定义如表 1 所示。

表 1 中， Code 由数据库提供的 INT 整型或 STRING 类型存储， 支持三维网格编码和以编码 代数为基础的各种运算； Visible 是用一个数组列 来标记和存储计算得到的通视网格（集合）。

表 1 大表的结构定义 Tab.1 Structure of Big Table

| 列名        | 类型            | 说明                      |
|-----------|---------------|-------------------------|
| Code      | STRING/INT    | 三维网格编码                  |
| Visible   | STRING/INT[ ] | 通视网格编码                  |
| DataExist | INT           | 是否存有数据， 是为 1 ， 否为 0     |
| Data      | JSON[ ]       | 数据描述                    |
| Time      | TIME[ ]       | 数据时间， 包括进入网格 时间、 离开网格时间 |
| Source    | JSON          | 数据源描述                   |
| MetaData  | JSON          | 元数据信息                   |

## 1.3 卫星轨迹与资源网格化

## 1.3.1 卫星轨迹网格索引大表

本文根据卫星轨道根数与卫星星座的设计， 计算 出给定时间段内的卫星轨迹集合 &lt;Gridsat ， T &gt; （ Gridsat 为卫星轨迹的网格编码集合， T 为相应 时间段）。在原有的以卫星为组织形式的卫星轨 迹数据表的基础上， 结合轨迹集合改进对象表 （在原有表的基础上增加编码列， 并作为与索引 大表关联的外键）， 再与索引大表模型关联， 建立 卫星轨迹网格索引大表。在具体的卫星轨迹网 格化计算中， 由于卫星轨迹在卫星所在的轨道平 面运动， 涉及到卫星轨道的地心坐标系， 而空天 网格坐标是以经纬网格为基础发展的坐标体系， 因此先将地心坐标系（ x ， y ， z ）转为大地坐标系 （ L ， B ， H ）， 其中， L 为大地经度， B 为大地纬度， H 为高程； 再将大地坐标系转为空天网格坐标 code 。网格的尺度可以根据精度来选择（网格模 型共 32 层级）， 一般选择卫星的最小外包尺度匹 配的网格粒度 D layer 作为基础层级， 并选择其两层 父网格的粒度来进行初筛。卫星的位置和通视 关系为时变函数， 在具体计算时会按照卫星动目 标的运动轨迹在网格化时满足 D layer &lt; V 0 × T 的 原则（ V 0 为该时刻初速）， 即选择的最小时间间隔 为 T min = D layer / V 0 。具体在建立描述一颗卫星运 动轨迹的文档时， 需要包括卫星重要的基本信息 以及轨迹信息。

## 1.3.2 卫星资源能力索引大表

卫星资源能力索引大表是指将未来可获得 的卫星资源， 通过提前计算， 量化至空天网格坐 标中， 并以网格编码作为数据主键， 形成能力大 表（见图 1 ）。通过检索大表可知未来某时刻、 某 地面网格可以获取到哪些卫星数据［ 15 ］ 。其中， 空 间网格编码和时间建立联合索引， 一方面记录卫 星在不同时刻的地面覆盖情况， 另一方面为能力 大表快速检索作支撑。最终依托卫星资源能力

量化大表， 可以快速查询甚至地图可视化， 以及 未来不同时段、 不同区域会获取到的数据及获取 数据的对应卫星。当观测目标的形状是不规则 的， 则采用多尺度的网格集合来描述该地面对象 的空间范围， 其中不同层级的编码可以相互转换 （见图 2 ）。

1

这张图片展示了地球的一部分，并标注了未来5分钟内能获取数据的区域（绿色）和未来30分钟内能获取数据的区域（粉色）。右侧的地图显示了这些数据获取区域的全球分布情况。

<!-- image -->

这是一张表格，包含卫星编号、有效载荷编号、传感器类型等列。表格中有部分数据被红色圈出，可能是为了强调或说明。圈出的部分包含一些文字描述，但具体内容不清晰。

<!-- image -->

这张图片展示了一个表格，分为“对地覆盖范围空间编码”和“时间编码”两部分。表格中包含了一系列的二进制编码。

<!-- image -->

图 卫星资源能力索引大表

Fig.1 Satellite Resource Index Big Table

这张图片展示了两个图形。左边的图形是一个不规则的蓝色形状。右边的图形是左边图形的网格化版本，背景是网格，形状被填充为绿色，并且边缘用蓝色线条勾勒。

<!-- image -->

图 2 不规则目标的多尺度网格化 Fig.2 Multi⁃scale Gridding of Irregular Targets

# 2 星间互联网格化计算方法

在 §1 中的空天网格体系和空天全域网格索 引大表基础上， 本文提出了网格化星间互联计算 方法， 以用户获取特定区域的遥感卫星数据和未 来覆盖资源为例， 主要步骤如下： （ 1 ）通过预先计 算网格间的通视情况， 查找网格索引大表中的通 视情况和 GeoSOT -3D 二级索引来代替传统复杂 的通视计算方法。 （ 2 ）在无法直接通视的情况下 进行星间数据传输。建立网格化虚拟节点， 并使 用虚拟拓扑， 通过查询网格通视大表， 迭代出满 足覆盖要求的数据星间传输路径。

## 2.1 星间通视分析

卫星之间能够通信的最基本前提条件是卫 星的通视。影响卫星通视的主要因素有： 几何通 视、 天线通视、 距离影响 ［ 7 ］ 。其中， 几何通视是两 颗卫星不被地球遮挡， 天线通视是两颗卫星的天 线角度范围处于彼此天线夹角范围内， 距离影响 是指卫星通信会受功率及其他因素影响， 信号无 法传输。

卫星位置具有高时变特性， 因此， 本文选取 某一时刻 t 认为其此刻静止， 此时， 卫星 A 、 B 之间 的距离为 l AB ， 轨道高度分别为 d A 、 d B ， 地球半径厚 度分别为 R earth 。卫星之间的几何可见性示意图 如图 3 所示。

图 3

这张图片展示了一个地球和两颗卫星的几何关系图。图中地球位于中心，标记为“地球”，半径为$R$。两颗卫星分别标记为“卫星A”和“卫星B”，它们与地球中心的连线分别标记为$d_A$和$l_{AB}$。卫星A和卫星B与地球中心的连线之间的夹角标记为$\theta_B$。图中还标注了卫星A和卫星B的可见与不可见区域，以及地球表面的高度$h$。

<!-- image -->

卫星之间几何可见性示意图 Fig.3 Diagram of Geometric Visibility Between Satellites

为了构建网格化星间通视分析二级索引， 先 查询网格大表中的通视网格， 若通视， 则再进行 方位、 距离等计算分析。

## 2.1.1 通视网格查找表

索引大表的表结构定义在 §1.2 中已经给出， 其中包含 Visible 字段， 该字段为数组结构， 可以 为一个或多个值， 即存储网格所对应的通视网格 集合。

通视网格是原网格的固有属性， 无论网格有 没有数据， 都会有对应的通视网格。当查询一个 网格的通视网格， 输入查询语句即可。通过获取 Visible 字段可知， 一个网格可能会有非常多的几 何通视网格。由于卫星上的存储资源有限， 因此 对通视大表进行优化非常有必要。卫星运动具 有周期性， 因此进行存储优化时， 可以将某一个 卫星在不同时刻的所有通视网格存入星上， 根据 周期的运行时间来匹配几何通视网格即可。如 考虑卫星轨道的摄动等影响， 可以定期去后台计 算并更新通视网格。

## 2.1.2 网格通视计算

网格几何可视性计算的原理是依托网格编

码代数， 基于三维 Bresenham 算法， 结合网格的多 尺度特性， 进行网格填充 ［ 16 ］ 。首先填充较大尺度 的网格， 通过不断判断连续填充网格在三维空间 中更偏离的方向， 确定边相邻、 角相邻的网格， 再 进一步划分小尺度网格， 实现递进式划分填充。 特别地， 可以将上一层级的路径结果进行分割， 对每个子路径进行并行计算， 来计算星间链路网 格集合， 提升计算效率。然后通过高度码判断是 否被地球遮挡（只需比较网格编码集合最小高程 码与遮挡高度高程码大小即可）， 从而实现卫星 间几何可见性判断。

上述算法的优势在于不存在判断是否同轨 等问题（不同轨道计算复杂）， 且化高维浮点数计 算为一维高度码比对。在预先计算好一个网格 的所有通视网格后， 就可以存入网格通视查找 表， 成为该网格的固有属性。当一颗卫星出现在 另一颗卫星所在网格的通视网格中， 则两颗卫星 处于几何通视状态。

此外， 还可以在几何通视分析基础上， 基于 网格编码的方位运算、 距离量算函数进行天线通 视、 距离影响分析， 例如通过设置网格属性， 对大 气层部分网格设置权重， 在计算通透性时加入权 重， 细化模型， 最终实现星间通视精细计算。

## 2.2 星间路由空间链路动态规划

低轨卫星星座由上百颗卫星组成， 若在该系 统中只采用时间分片的集中式 + 路由算法， 星上 存储和计算压力较大， 且在发生紧急突发情况 时， 应急效率和可靠性较低。因此， 需要进一步 结合低轨卫星星座的特点， 设计一套适合于卫星 网络拓扑的模型与路由算法。

## 2.2.1 网格化网络拓扑模型

首先对低轨卫星星座建立基于网格的分布 式路由基本模型。核心思路是将地球表面划分 为不同区域， 即 GeoSOT -3D 的网格划分， 每个区 域分配一个虚拟节点（ virtul node ， VN ）， 标记为 该网格的网格编码（见图 4 ）。

4

图片展示了一个网络连接示意图。用户1发送请求，通过网络自身实现虚拟连接，接入控制，最终到达用户2。图中还显示了路由路径。

<!-- image -->

图 网格化虚拟节点 Fig.4 Grid Virtual Node

卫星在网格内时， 这个网格对应的网络节点 则被该卫星持有； 当卫星离开时， 也会失去与网 格的持有关系。当卫星从邻近的区域进入该区 域时， 在本算法中就是从邻域网格进入， 同样离 开该网格也是前往邻域网格。进入网格化的路 由时， 虚拟节点会对邻域的 6 个方向即上、 下、 左、 右、 前、 后进行判断， 采用全球坐标系则为顶、 底、 西、 东、 北、 南 6 个方向， 分别对应网格的六邻域 （见图 5 ）。当选择好合适的邻域网格后， 进行下 一跳， 称为方向增强。当卫星进入该网格， 则会 匹配该网格的网格码， 从而获取对应的路由表及 网格相关信息。结合空天全域网格索引大表模 型， 即卫星进入一个网格， 直接查找索引大表中 网格编码关联的信息即可。

Fig.5 Six Neighborhood Grids

这是一张展示网格六邻域的示意图。图中显示了一个三维立方体结构，其中包含一个中心立方体和其周围的六个相邻立方体。坐标轴分别标记为 \(h\)、\(L\) 和 \(\beta\)。

<!-- image -->

卫星的网格虚拟节点还可以按照应用场景 需求继续划分， 分为子网格， 一个虚拟节点可以 包含一个子网格集合。在每个网格虚拟节点中 心的小网格可表示这个虚拟节点目前被哪个卫 星所占有。地面上的地面站或者用户也可以作 为节点映射在网格单元中， 而这些网格单元是固 定的。 GeoSOT -3D 网格体系的二三维一致性很 好地支持了地面、 卫星网格节点保持一致特性。 2.2.2 星间路由空间链路动态规划

动态规划算法是用来解决多阶段、 多任务、 多目标决策过程中如何最优化这一问题的经典 算法［ 17 ］ 。

本文基于网格化网络拓扑思路， 对研究时段 的卫星运行周期 T 进行分区， 分为 K 个时间段， 当时段（ Δ t = T / K ）足够小， 可以认为时段内的卫 星拓扑结构不变， 此时可将卫星拓扑结构看作所 在网格的拓扑结构。在每个时间段内， 建立包含 卫星和地面目标拓扑结构信息的关联矩阵， 整个 关联矩阵大小为（ M + N ） × （ M + N ） （其中 M 、 N 分别代表建立卫星、 地面目标的数量）； 卫星拓扑 的主关联矩阵存在星上， 定期更新。基于该矩阵

进行最短路径算法， 其时间复杂度、 空间复杂度 为 O （ （ M + N ） 2 ）。当卫星数目、 地面目标数目较 多时， 计算和存储的代价太大， 不符合星上要求。 由于通视是通信的必要不充分条件， 因此在每次 建连接图时， 增加一步查询通视表的步骤， 筛掉 不通视、 更不可能通信的卫星， 建立一个小规模 的关联矩阵， 降低算法特别是星上存储的代价。 再根据最小跳数、 最短距离等不同决策来选择 路径。

由于在计算过程中一定存在无关卫星， 故新 建立的关联矩阵的大小一定小于（ M + N ） × （ M + N ）。剔除每个时间片下没有参与通信的无 关卫星， 降低主关联矩阵的维数， 减少最短路径 算法的寻路时间， 极大降低了最短路径算法的时 间复杂度和空间复杂度。

# 3 仿真实验

## 3.1 实验设计

根据研究内容与方法， 本文将进行以下 3 组 实验： （ 1 ）构建空天网格索引大表； （ 2 ）星间通视 分析； （ 3 ）星间路由空间链路动态规划。

实验数据采用仿真 Walker 星座， 构型为 90/ 15/2 ，共 15 个轨道面，每个轨道面 6 颗卫星， Satellite ij 代表星座的第 i 轨道面的第 j 颗卫星。模 拟开始时间为协调世界时 2019 -02 -16T04 ： 00 ： 00 -2019 -02 -17T04 ： 00 ： 00 。采用卫星工具箱（ satellite tool kit ， STK ）生成仿真星座， 坐标系为 J2000 。

## 3.2 空天网格索引大表

网格索引大表实验包括网格化、 存储、 建立 索引 3 个步骤。按照卫星轨迹网格化方法， 对仿 真星座的 90 颗卫星在该时段的轨迹进行网格化， 存入表中。首先对 90 颗卫星分别进行轨迹网格 化。根据卫星轨道根数（ two lines of elements ， TLE ）计算卫星各时刻空天网格坐标， 并使用线 对象网格建模、 三维路径填充算法建立整个卫星轨 迹的网格映射。将 Walker 仿真星座及 GeoSOT -3D 在 Cesium 平台中进行可视化， 结果见图 6 。然 后将计算的数据结果生成为 JSON 类型， 批量导 入数据库， 通过网格编码与空天网格索引大表的 编码主键进行关联； 再对编码列建立空时二级索 引， 以加速查询。

## 3.3 星间通视分析

星间通视是判断两颗卫星是否可以通过地 球通视， 即任意两颗卫星其连线与地球不相交。 在仿真星座中，随机选取 10 、 20 、 30 、 40 、 50 、 60 、

70 、 80 、 90 颗卫星， 计算每个经纬度高程坐标在第 15 层级的网格编码， 并进行网格通视大表的效率 对比。利用网格通视大表与网格几何通视算法、 传统的几何通视算法进行星间通视计算， 各自的 用时如图 7 所示。

图 6 卫星轨迹、 覆盖网格可视化 Fig.6 Satellite Trajectory and Coverage Grid Visualization

这是一张显示地球的图片，地球被描绘成透明的，可以看到内部结构。图片上标注了多条轨道，可能代表卫星或航天器的运行路径。地球表面的陆地和海洋清晰可见，背景是黑色的宇宙空间。

<!-- image -->

这是一张世界地图，显示了各大洲和海洋。地图上有一条粉红色的曲线，连接了不同的地点。地图的左上角有一个图例，解释了曲线的含义。

<!-- image -->

图 7 3 种通视计算方法的效率对比

这是一张柱状图，展示了不同卫星数量下三种计算方法的计算时间。图中包括“网格通视大表”、“网格几何通视算法”和“传统几何通视算法”三种方法。横轴表示卫星数量，纵轴表示计算时间（单位为微秒）。

<!-- image -->

Fig.7 Comparison of Time⁃Consuming of Three Visibility Calculation Methods

从图 7 中可以看出， 采用经纬高计算任意两 点之间的通视情况与星间计算次数相关， 且呈指 数上升， 通视计算时间大于网格通视计算。而采 用网格编码， 只需在计算两点连线网格中有任意 一个网格高程码为负即可， 避免了复杂的空间运 算， 较传统算法提升 2.2 倍。由于网格坐标单元 相对地心是固定的， 因此可以提前计算出网格与 其他网格之间的通视关系， 当卫星分别进入已明 确通视关系的若干网格内， 只需要查询提前计算 好的网格通视查找表即可。通过预先计算的网 格通视大表， 查询网格的通视网格， 较传统算法

提升 20.9 倍。

为了分析本文算法复杂度， 在星间通视分析 的常规算法中， 首先假设空中存在 N 颗卫星， 对 于每颗卫星， 都要与其他卫星进行距离量算， 测 算其角度是否在可视范围内， 高程又是否与地球 有遮挡， 时间复杂度为 O （ N ）； 基于通视网格大表 查询： 利用网格计算模型时， 卫星的三维空间坐 标以编码的形式存储在数据库中， 查询的时间复 杂度是 O （ log N ）， 大大降低了算法复杂度。虽然 本文方法在计算前采用了 '空间换时间' 的思路， 首先构建空天网格索引大表并预判网格之间的 通视关系， 有一定开销（本实验中基于编码的存 储空间为离散化传统方法的 7.8 倍）， 但在完成大 表构建后， 在面向 PNTRC 系统数百颗卫星甚至 更大规模的卫星星座时， 卫星数量的大量增加对 算法计算量的影响应远比传统方法小， 在星间互 联计算等方面具有效率优势。同时， 结合网格的 多尺度特性， 通过粗粒度网格的初步筛选， 可以 更快速筛选到通视网格大致范围， 之后进行尺度 的细化以及天线夹角等角度量算网格化算法， 计 算的准确率也得以保障。

## 3.4 星间路由空间链路动态规划

基于空天网格化建模， 按照时间进行等距划 分， 每个时间段认为是静态的， 根据网格自身之 间的可视性（查找表）来判断落入不同网格内卫星 之间的通视情况， 生成卫星路由关联矩阵。设定地 面信号点为深圳市某点（ 114°E ， 22°N ， 100 m ）， 根 据可见拓扑关系， 建立卫星之间的连接图（ 1 为可 见， 1 为不可见）。根据最短路径、 最小跳数的 策略选择， 计算出最短的路由路径： 当星座规模 变大时， 如选择 90 颗卫星， 两个不同策略下的路 径存在不同， 具体用时如图 8 所示。

图 8 星间路由空间链路动态规划效率对比 Fig.8 Time⁃Consuming Comparison of Route Planning

这张图片展示了一个柱状图，比较了不同算法的计算时间。图中包括四种算法：网格化最短路径算法、网格化最小跳数算法、常规最短路径算法和常规最小跳数算法。横轴表示卫星数目，纵轴表示计算时间（单位为微秒）。

<!-- image -->

由图 8 可知， 网格化算法的效率显著优于传 统算法的， 在最短距离约束的路径规划中， 效率 平均提升近 25 倍； 在最小跳数中， 提升约 20 倍。

另外， 在实际应用中， 还应考虑链路情况的 复杂性以及延时、 干扰等因素。后续研究应该结 合实际应用中可能的多种影响因素， 进行更为精 确的分析。

# 4 结 语

本文在天基大数据背景下， 结合低轨卫星星 座， 特别是 PNTRC 系统建设， 引入 GeoSOT -3D 模型， 并将其应用到航空航天范围， 探讨低轨大 规模、 复杂网络环境的卫星星座信息快速回传方 法。通过构建空天全域网格索引大表， 提出了星 间互联网格计算方法， 建立以网格编码为主键的 空天全域网格索引大表来关联空天位置信息； 实 现星间通视分析的网格通视查找表及网格通视 计算二级检索模型； 对于境外卫星资源无法直接 传输给地面用户时， 需要进行星间数据传输， 即 先建立网格化虚拟节点， 并使用虚拟拓扑， 通过 查询网格通视大表， 迭代出满足覆盖要求的数据 星间传输路径。实验从建立空天网格索引大表 开始， 验证了组织、 存储、 计算、 规划这一星间互 联计算及应用流程的可行性与高效性， 该 '空间 换时间' 的方法在星间互联计算等方面具有效率 优势， 考虑实际物理开销后， 判断卫星连线网格 编码是否为负的网格通视分析效率较传统算法 提升 2.2 倍， 基于预先建立通视大表的通视分析 效率较传统算法提升 20.9 倍， 网格化星间路由规 划效率在最短距离约束下提升近 25 倍， 在最小跳 数约束下则提升约 20 倍。在完成大表构建后， 卫 星数量的大量增加对算法计算量的影响远比传 统方法小， 更适用于大规模、 复杂低轨卫星间的 通信与传输。

本文提出的网格化星间互联算法， 其应用与 发展将为低轨大规模、 复杂网络通信的卫星星座快 速互联、 信息回传提供解决方案； 同时由于网格具 有二三维一致性， 对星上、 地面计算均可提供有效 支持， 有利于构建基于位置的天地一体化网络通 信， 实现更高效的天基信息智能服务。然而， 由于 本文首次将网格体系用于低轨卫星星座的互联算 法， 仍有很多问题值得深入研究， 如大气层对信号 传递距离影响的精细计算、 空天全域网格索引大表 的索引优化、 针对星上算法的存储优化、 星间路由 动态规划的多任务多目标算法优化等方向。

## 参 考 文 献

- ［ 1 ］ Yang Y ， Li J ， Xu J ， et al. Contribution of the Com⁃ pass Satellite Navigation System to Global PNT Users ［ J ］ . Chinese Science Bulletin ， 2011 ， 56 （ 26 ）： 2 813 -2 819
- ［ 2 ］ Li Deren. Towards Geospatial Information Technolo⁃ gy in 5G/6G Era ［ J ］ . Acta Geodaetica et Carto⁃ graphica Sinica ， 2019 ， 48 （ 12 ）： 1 475 -1 481 （李德 仁 . 展望 5G/6G 时代的地球空间信息技术［ J ］ . 测 绘学报， 2019 ， 48 （ 12 ）： 1 475 -1 481 ）
- ［ 3 ］ Liu Chunbao. Overview of the Development of Foreign Navigation Satellites in 2018 ［ J ］ . Space International ， 2019 （ 2 ）： 42 -47 （刘春保 . 2018 年国 外导航卫星发展综述［ J ］ . 国际太空， 2019 （ 2 ）： 42 -47 ）
- ［ 4 ］ Chen Ruizhi ， Wang Lei ， Li Deren ， et al. A Survey on the Fusion of the Navigation and the Remote Sensing Techniques ［ J ］ . Acta Geodaetica et Carto⁃ graphica Sinica ， 2019 ， 48 （ 12 ）： 1 507 -1 522 （陈锐 志，王磊，李德仁，等 . 导航与遥感技术融合综述 ［ J ］ . 测绘学报， 2019 ， 48 （ 12 ）： 1 507 -1 522 ）
- ［ 5 ］ Li Deren ， Shen Xin ， Gong Jianya ， et al. On Con⁃ struction of China ' s Space Information Network ［ J ］ . Geomatics and Information Science of Wuhan Uni⁃ versity ， 2015 ， 40 （ 6 ）： 711 -715 （李德仁，沈欣，龚健 雅，等 . 论我国空间信息网络的构建［ J ］ . 武汉大学 学报·信息科学版， 2015 ， 40 （ 6 ）： 711 -715 ）
- ［ 6 ］ Li Deren ， Shen Xin ， Li Dilong ， et al. On Civil -Mili⁃ tary Integrated Space ⁃ Based Real -time Information Service System ［ J ］ . Geomatics and Information Science of Wuhan University ， 2017 ， 42 （ 11 ）： 1 501 -1 505 （李德仁，沈欣，李迪龙，等 . 论军民融合的卫 星通信、遥感、导航一体天基信息实时服务系统 ［ J ］ . 武汉大学学报·信息科学版， 2017 ， 42 （ 11 ）： 1 501 -1 505 ）
- ［ 7 ］ Sharaf M A. Satellite to Satellite Visibility ［ J ］ . Open Astronomy Journal ， 2012 ， 5 （ 1 ）： 26 -40
- ［ 8 ］ Sun L ， Wang Y ， Huang W ， et al. Inter -satellite Communication and Ranging Link Assignment for Navigation Satellite Systems ［ J ］ . GPS Solutions ， 2018 ， 22 （ 2 ）： 38 -47
- ［ 9 ］ Sanctis M D ， Cianca E ， Bisio I ， et al. Satellite
- Communications Supporting Internet of Remote Things ［ J ］ . IEEE Internet of Things Journal ， 2016 ， 3 （ 1 ）： 113 -123
- ［ 10 ］ Xu Hui ， Fei Huang ， Wu Shiqi. A Distributed QOS Routing Based on ANT Algorithm for LEO Satellite Network ［ J ］ . Journal of Electronics ， 2007 ， 24 （ 6 ）： 765 -771
- ［ 11 ］ Goodchild M F. Discrete Global Grids ： Retrospect and Prospect ［ J ］ . Geography and Geo ⁃ Information Science ， 2012 ， 28 （ 1 ）： 1 -6
- ［ 12 ］ Cheng Chengqi ， Ren Fuhu ， Pu Guoliang ， et al. In⁃ troduction to Spatial Information Subdivision and Organization ［ M ］ . Beijing ： Science Press ， 2012 （程承 旗，任伏虎，濮国梁， 等 . 空间信息剖分组织导论 ［ M ］ . 北京：科学出版社， 2012 ）
- ［ 13 ］ Cheng C ， Tong X ， Chen B ， et al. A Subdivision Method to Unify the Existing Latitude and Longi⁃ tude Grids ［ J ］ . ISPRS International Journal of Geo⁃ Information ， 2016 ， 5 （ 9 ）： 161 -183
- ［ 14 ］ Li Shuang ， Cheng Chengqi ， Tong Xiaochong ， et al. A Study on Data Storage and Management for Massive Remote Sensing Data Based on Multi -level Grid Model ［ J ］ . Acta Geodaetica et Cartographica Sinica ， 2016 ， 45 （ S1 ）： 106 -114 （李爽，程承旗，童 晓冲，等 . 基于多级信息网格的海量遥感数据存储 管理研究［ J ］ . 测绘学报， 2016 ， 45 （ S1 ）： 106 -114 ）
- ［ 15 ］ Zhang Wei ， Wang Shoubin ， Cheng Chengqi ， et al. A Multi -satellite Resource Integration Organization Model Based on Girds ［ J ］ . Geomatics and Informa⁃ tion Science of Wuhan University ， 2020 ， 45 （ 3 ）： 331 -336 （张玮，王守斌，程承旗，等 . 一种卫星资 源一体化网格组织模型［ J ］ . 武汉大学学报·信息科 学版， 2020 ， 45 （ 3 ）： 331 -336 ）
- ［ 16 ］ Au C ， Woo T. Three Dimensional Extension of Bresenham ' s Algorithm with Voronoi Diagram ［ J ］ . Computer⁃aided Design ， 2011 ， 43 （ 4 ）： 417 -426
- ［ 17 ］ Yao Ye ， Liang Xuwen. Dynamic Routing Tech⁃ nique Based on LEO &amp; GEO Double -Layered Satellite Network ［ J ］ . System Engineering and Electronics ， 2013 ， 35 （ 9 ）： 1 966 -1 973 （姚晔，梁 旭文 . LEO&amp;GEO 双层卫星网络的动态路由技 术［ J ］ . 系统工程与电子技术， 2013 ， 35 （ 9 ）： 1 966 -1 973 ）

## Aerospace Grid⁃Based Algorithm of Inter⁃satellite Visibility and Route Path Planning for Satellite Constellation

LI Shuang 1 LI Deren 2 CHENG Chengqi 3 CHEN Bo 3 SHEN Xin 2 TONG Xiaochong 4

```
1 Research Center of Historical Geography, Fudan University, Shanghai 200433, China 2 State Key Laboratory of Information Engineering in Surveying, Mapping and Remote Sensing, Wuhan University, Wuhan 430079, China 3 College of Engineering, Peking University, Beijing 100871, China 4 Institute of Surveying and Mapping, Information Engineering University, Zhengzhou 450001, China
```

Abstract ： The construction of space⁃based information service system integrating positioning, navigation, timing, remote sensing and communication (PNTRC) will provide a powerful guarantee for cross⁃border real ⁃ time communication, global tracking of moving targets, and rapid response to disasters. It also puts forward new requirements for efficient network communications, especially satellite routing planning algorithms. In order to optimize the communication link and reduce the time delay, this paper makes full use of the advantages of direct view between spatial grids and high coding calculation efficiency, and pro⁃ poses a satellite grid space grid computing method. This paper introduces the GeoSOT⁃3D grid subdivision model and applies it to the aerospace, proposes an aerospace grid index big table, and develops a set of satellite visibility analysis and inter⁃satellite routing planning by querying the grid visibility look⁃up table. In order to verify the feasibility and applicability of the proposed algorithm, based on the coding generation principle and visualization of the aerospace grid coordinate test platform, a global grid index big table is established. Three sets of verification work are carried out after simulating the 90/15/2 Walker constella⁃ tion, including grid big table experiment, inter⁃satellite calculation efficiency experiment, and inter⁃satellite route planning experiment. The experiments verify the feasibility of the inter ⁃ satellite link calculation and application process in terms of organization, storage, calculation and planning. The efficiency of grid visibili⁃ ty analysis to determine whether the satellite connection grid code is negative is 2.2 times higher than the traditional algorithm, and the efficiency of the visibility analysis based on the pre⁃established universal visi⁃ bility table is 20.9 times higher than the traditional algorithm. The efficiency of grid ⁃ based inter ⁃ satellite routing planning is improved by nearly 25 times under the shortest distance constraint, and approximately 20 times under the minimum hop count constraint. Through theoretical analysis and experimental verifica⁃ tion, it is initially shown that the algorithm is feasible and efficient. We hope that the proposed algorithm can be used in emergency communications, disaster warning, maritime rescue, etc., and also contribute to the construction of satellite Internet.

Key words ： aerospace information grid ； aerospace grid index big table ； satellite visibility analysis ； satellite route path planning

First author: LI Shuang, PhD, associate professor, specializes in spatiotemporal grid model and historical GIS. E⁃mail: li\_shuang@fudan. edu.cn

Corresponding author: CHENG Chengqi, PhD, professor. E⁃mail: ccq@pku.edu.cn

Foundation support: The National Key Research and Development Program of China (2018YFB0505300) ； Research Start⁃up Foundation for Introduced Talents in Fudan University (JIH3142004).

引文格式： LI Shuang,LI Deren,CHENG Chengqi,et al.Aerospace Grid⁃Based Algorithm of Inter⁃satellite Visibility and Route Path Plan⁃ ning for Satellite Constellation[J]. Geomatics and Information Science of Wuhan University, 2021, 46(1): 50 -57. DOI: 10.13203/j. whu⁃ gis20200234 （李爽 , 李德仁 , 程承旗， 等 . 空天网格化星间通视及路由路径规划算法 [J]. 武汉大学学报·信息科学版 ,2021,46(1):50 -57. DOI:10.13203/j.whugis20200234 ）
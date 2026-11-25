# 乡村弹幕投影节奏场测

江幕夜间艺术组在不同乡镇投影点复用节奏，先比较真实拍点序列，再核查计量和切换分路。

## 现场工作与联系人

模拟客户为江幕夜间艺术组。灯光 cue 序列、场地试投偏差、节奏簇、对场 cue 合用；跨场地电表协议不同拒绝合用，记录分路提示。

- 场地配电和投影线 `venues`，字段为 `protocol`（计量协议）、`channels`（可用分路）、`ready`（已签场地）。模型约束位于 `backend/domain/venues_model.py`，规则位于 `venues_service.py`。
- 试投节奏轨迹 `cue_tracks`，字段为 `venue`（场地）、`timings`（原始拍点序列）、`shift`（总偏移秒）、`locked`（模板已见证）、`clock`（原时钟/换钟）、`metronome`（计拍器）、`measured_at`（测量时间）、`calibration`（认用标定）、`converted_timings`（换算到原钟口径的拍点）。模型约束位于 `backend/domain/cue_tracks_model.py`，规则位于 `cue_tracks_service.py`。
- 换钟标定 `clock_calibrations`，字段为 `metronome`（计拍器）、`valid_from/valid_to`（测量时段）、`pairs`（同段新旧拍点）、`scale/offset`（拟合的时钟比例与偏移）、`max_error`（检验段最大误差）、`enabled`（是否启用）。拟合逻辑位于 `backend/domain/calibration.py`，规则位于 `clock_calibrations_service.py`。
- 对场节奏簇 `cue_clusters`，字段为 `track`（输入素材）、`representative`（簇样板）、`distance`（DTW 距离）、`members`（簇内轨迹）、`token`（计算凭据）、`calibration`（签簇沿用的标定）。模型约束位于 `backend/domain/cue_clusters_model.py`，规则位于 `cue_clusters_service.py`。
- 交场分路回单 `cue_routing`，字段为 `cluster`（节奏簇）、`destination`（目标场地）、`route`（物理分路）、`status`（交场状态）。模型约束位于 `backend/domain/cue_routing_model.py`，规则位于 `cue_routing_service.py`。

团队为模拟的8 人夜间艺术团队，负责村站联动试投与线路确认。

现场用一张纸记拍点、另一张纸记分路。相近节奏难手工比对，跨场计量口径容易串用，目标场已占分路经常要现场重分配。

已确认的试投片段进入 DTW 比较，联动岗领取合用回单或独立分路提示。

换过计拍器后各台拍点对不上时，先在试投页用同段新旧拍点拟定时钟比例与偏移：末段约四分之一拍点留作检验，检验最大误差超过 0.1 秒的标定只收存不启用。标定按计拍器和测量时段（半开区间）生效，同一计拍器时段重叠的两份标定即使同时提交也只启用一份。未标定的换钟原件先收存（原拍点照录、换算留空），标定晚到时可按测量时间补认；原时钟素材照用，换钟素材经标定和见证后才可对场。签簇沿用比较受理那一刻的换算，签后可在台账查原件与所用标定。

### 一天的业务操作

1. 16:20 对 HALL-A 输入六个实测拍点（原时钟素材照用）。
2. 16:30 用同段新旧拍点提交换钟标定，留段检验通过后启用。
3. 16:40 经放映领班见证锁定；未标定的换钟原件先收存，标定到位再补认。
4. 17:30 比对 15 条素材（换钟素材按受理时的换算进入 DTW）。
5. 18:20 签认 BEAT-24 节奏簇，簇上留存沿用的标定号。
6. 19:00 HALL-B 协议区别触发分路提醒。
7. 19:30 HALL-C 通过 MTR-030，签发 C-1 合用回单。

## 启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

打开 `http://127.0.0.1:18329`。FastAPI OpenAPI 在 `http://127.0.0.1:19329/docs`。
Compose 运行 Nginx、Python FastAPI、独立 Redis 消费进程、SQL 数据库和 Redis，SQL 与 Redis 使用命名卷。
本机开发时，在 Python 3.11 环境安装 `backend/requirements.txt` 后从 backend 目录运行 `uvicorn core.app:app`。须提供 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET`，`SEED_DEMO` 控制演示初始化。

| 演示账号 | 权限 |
|---|---|
| operator@demo.test | 提交领域记录和计算请求 |
| reviewer@demo.test | 提交记录并执行有业务约束的复核操作 |
| viewer@demo.test | 浏览业务台账 |

三个本地演示账号均使用 `DemoC0de!2026`。角色在 `backend/core/roles.py` 和 `frontend/src/store.js` 中声明。计算状态在 worker、queueing、API 和同一前端 store 中使用。

## 页面与接口

| 业务任务 | FastAPI 路由 | 页面 |
|---|---|---|
| 场地配电和投影线 | `/venues` /venues/sign-venue | `frontend/src/pages/venues.js` |
| 试投节奏轨迹 | `/cue_tracks` /cue_tracks/record-track，/cue_tracks/resolve-calibration，/cue_tracks/lock-track | `frontend/src/pages/cue_tracks.js` |
| 计拍器换钟标定 | `/clock_calibrations` /clock_calibrations/submit-calibration | `frontend/src/pages/cue_tracks.js` |
| 对场节奏簇 | `/cue_clusters` /cue_clusters/compare-cues，/cue_clusters/save-cluster | `frontend/src/pages/cue_clusters.js` |
| 交场分路回单 | `/cue_routing` /cue_routing/share-cue，/cue_routing/record-separate | `frontend/src/pages/cue_routing.js` |

SQL 实体与约束在 `backend/domain` 下维护。前端使用原生 ES modules。核心算子为 DTW + 凝聚层次聚类。以绝对时间差为局部代价，DTW 归一化后作为层次聚类的距离矩阵，簇内总距离最短的轨迹为代表。换钟标定的时钟比例与偏移用最小二乘拟合 `旧钟 = scale × 新钟 + offset`，末段拍点留作检验，阈值 0.1 秒。已存在的库表由 `core/schema_migrate.py` 在启动时幂等补齐新增列，新库由 `metadata.create_all` 直接建出完整结构。后端测试位于 `backend/tests`（拟合纯逻辑、SQLite 服务层集成、HTTP 冒烟）。

拍点与场地端为模拟记录。应用产出路线回单，无线路开关控制。

[MIT](LICENSE)

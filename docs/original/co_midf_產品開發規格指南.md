# CoMIDF 全產品開發規格指南（Product Development Specification）

> **目的**：本指南為 CoMIDF 系列產品（Edge Agent + MSSP Cloud 平台）的完整開發規格，供工程師與 Vibe Coding AI 依據此文件進行系統設計、程式開發、部署與測試。
>
> **語言慣例**：
> - 程式碼與 API 名稱：English only
> - 文件與解釋文字：繁體中文
>
> **主要構成模組**：
> - Edge Layer（地端代理層）
> - Cloud Layer（雲端 MSSP 平台）
> - Integration Layer（CTI / XDR / SOAR）
> - Management Layer（租戶與配置管理）

---

## 1. 系統總覽
CoMIDF 為一個 **多協定協作式入侵偵測框架**，可同時監控 HTTP(S)、MQTT、CoAP、Modbus、Zigbee、QUIC 等協定，並利用 **機率融合引擎（Bayesian + Dempster–Shafer）** 在雲端進行跨協定推論。系統採用模組化架構，支持地端輕量代理與雲端集中分析模式。

---

## 2. 架構分層

| 層級 | 模組 | 功能概要 | 技術棧 |
|------|------|------------|---------|
| Edge Layer | Protocol Agents, FAL, Secure Connector | 擷取封包、特徵萃取、UER 封裝、上傳 | Python / Rust / gRPC / TLS 1.3 |
| Cloud Layer | GC, PR, AFL, Correlation Engine | 多租戶融合推論、策略回饋、事件可視化 | FastAPI / Kafka / PostgreSQL / Redis / Docker |
| Integration Layer | CTI & XDR Connectors | 與外部安全平台資料整合 | OpenCTI / MISP / STIX 2.1 / TAXII |
| Management Layer | Portal / Auth / Billing | 租戶管理、使用者權限、SLA 控制 | React / Keycloak / Grafana / Elastic Stack |

---

## 3. 系統功能需求（Functional Requirements）

### A. Edge Layer
1. 多協定協作監控（HTTP, MQTT, CoAP, Zigbee, QUIC）
2. 自動特徵抽取與統一事件轉換（UER）
3. 線上/離線模式運作與自動補送
4. 與雲端 GC 雙向安全連線（mutual TLS + Token）
5. 接收策略回饋並自動套用

### B. Cloud Layer
1. 即時 UER 接收與事件佇列化（Kafka）
2. 機率融合推論引擎（Bayesian + DS）
3. 多租戶資料隔離與統計儀表板
4. 自動化警示與策略下發（AFL）
5. SOC / MSSP 報表輸出（PDF / API）

### C. Integration Layer
1. CTI Feed 對接（MISP / OpenCTI）
2. IOC 匹配與 ATT&CK 映射
3. XDR 平台警示整合（Cynet / Cortex XSOAR / Splunk Phantom）

### D. Management Layer
1. 租戶註冊與驗證
2. API 金鑰與憑證管理
3. 使用量統計與計費模組
4. 使用者分層權限與審計追蹤

---

## 4. 資料流與通訊協定
```
Edge → FAL → Secure Connector → Cloud Gateway (Ingress) → Kafka → GC → PR → AFL
                                                        ↓
                                                    Storage (Postgres/ES)
                                                        ↓
                                                 Portal / Dashboard
```
**通訊規格**：HTTPS/gRPC over TLS 1.3、Bearer Token + X-Tenant-ID Header。

**資料格式**：UER JSON Schema（統一事件記錄）— 詳見 Edge Agent 開發指南。

---

## 5. 雲端服務模組規格

### 5.1 Global Correlator (GC)
- 任務：整合多協定事件、以機率模型融合各 Agent 輸出。
- 輸入：UER（包含 detector.score, conf, proto, stats）
- 輸出：Posterior (P(attack|E)) 與決策事件。
- 演算法：
  - Bayesian Fusion
  - Dempster–Shafer Evidence Combination
  - Dynamic Trust Weight Update

**程式設計介面**：
```python
def fuse_evidences(evidence_list: List[dict]) -> dict:
    """Return posterior and uncertainty"""
```

**效能要求**：
- 平均延遲 < 100ms；每節點可處理 20k UER/s。

### 5.2 Policy & Response (PR)
- 任務：將 GC 的結果轉換為安全動作（alert, isolate, enrich）。
- 介面：REST `/api/alerts`, `/api/actions`。
- 支援輸出：Syslog, Webhook, SOAR API, Email。

### 5.3 Active Feedback Loop (AFL)
- 任務：依 GC 準確率調整各 Agent 的 trust、threshold、sampling。
- 執行頻率：5 分鐘 / 週期。
- 通訊：HTTPS POST → Edge `/feedback` 或 Edge Pull。

### 5.4 Cloud Gateway (Ingress)
- 任務：接收上傳的 UER 並投遞 Kafka。
- 驗證：JWT Token + TLS；記錄租戶 ID。
- 輸出：Kafka topic `uer.ingest.<tenant_id>`。

---

## 6. 數據庫與儲存設計
| 資料庫 | 功能 | 模式 |
|----------|--------|------|
| PostgreSQL | Metadata, Tenant, Auth, Policy | Relational |
| Elasticsearch | 快速搜尋 UER, 可視化 | Document |
| Redis | 快取 AFL 回饋、指令佇列 | In-memory |
| MinIO/S3 | 長期封包或報表儲存 | Object |

**主鍵範例**：
```
uer_id = sha256(ts + tenant + src_ip + dst_ip + model)
```

---

## 7. 多租戶設計（Multi-Tenancy）
- 每租戶擁有獨立 Namespace：Kafka topic, DB schema, TLS 憑證。
- 雲端 Gateway 根據 X-Tenant-ID 判定命名空間。
- Dashboard 僅呈現同租戶資料；
- AFL 回饋以租戶隔離策略發送。

---

## 8. 安全與隱私要求
- 上傳資料不含 Payload；僅包含側信道特徵。
- 所有識別符（device_id, hostname）以 SHA256+salt 匿名化。
- 傳輸加密：TLS 1.3 + AES-256。
- 身份驗證：JWT + mTLS。
- 審計：所有上傳與策略變更記錄 Audit Trail。
- 合規：支援 GDPR / ISO 27001 / CSA STAR。

---

## 9. 監控與觀察性（Observability）
**Metrics**：Prometheus + Grafana。
- GC: `fusion_latency_ms`, `posterior_mean`, `agent_trust_avg`
- PR: `alerts_generated_total`, `actions_triggered_total`
- AFL: `feedback_sent_total`, `trust_update_avg`
- Edge: `uplink_success_rate`, `buffer_depth`

**Logs**：JSON 結構化，集中收集至 Elasticsearch。

---

## 10. 部署架構
- 雲端以 Docker Compose / Kubernetes 部署。
- 組件分層：
  - **Ingress Cluster** (接收 UER)
  - **Kafka Cluster** (資料匯流)
  - **Analysis Cluster** (GC/PR/AFL)
  - **DB Cluster** (Postgres/ES)
  - **Portal Cluster** (UI + API Gateway)

**擴展性**：K8s Horizontal Pod Autoscaler；Kafka topic 分區；GC 負載平衡。

---

## 11. 測試與驗收準則
| 測試類型 | 項目 | 標準 |
|-----------|------|--------|
| 單元測試 | 各模組功能 | 通過率 ≥ 90% |
| 整合測試 | Edge → Cloud → Feedback | 成功率 ≥ 99.9% |
| 壓力測試 | GC 輸入吞吐 | 20k UER/s / 節點 |
| 安全測試 | 模擬入侵、弱密碼、憑證錯誤 | 全部攔截 |
| 障礙測試 | 雲端中斷 10 分鐘 | Edge 自動補送 |

---

## 12. 文件與交付物
1. Edge Agent 開發指南（本指南配套）
2. 雲端 API 文件（OpenAPI 3.0 規格）
3. 架構圖與部署指南（K8s + Compose）
4. 測試報告模板（Test Plan / QA Report）
5. 運維手冊（Ops Manual, SOP, Backup/Restore）

---

## 13. 時程與分工建議
| 階段 | 任務 | 負責組別 | 時程 |
|------|-------|-----------|--------|
| Phase 1 | 架構 PoC (Edge ↔ Cloud) | Core Dev | 2 個月 |
| Phase 2 | 雲端多租戶 + Kafka 整合 | Cloud Team | 2 個月 |
| Phase 3 | GC 與 AFL 模型優化 | AI/ML Team | 1.5 個月 |
| Phase 4 | Portal 與報表系統 | Frontend/UI Team | 1.5 個月 |
| Phase 5 | 安全與壓測、文件化 | DevOps/Security | 1 個月 |
| Phase 6 | Beta 部署與試營運 | 全體 | 1 個月 |

---

## 14. 總結
此開發規格明確定義了 CoMIDF 產品從地端到雲端的所有元件、API、資料流程與測試要求。遵循本指南開發可確保：
- 系統具高可用性與擴展性；
- 支援多租戶 MSSP 營運；
- 滿足資安與隱私合規；
- 可持續優化為 AI 驅動之自適應防禦平台。

---

> 完成本規格文件後，Vibe Coding AI 與工程團隊可據此直接展開全系統開發、CI/CD、測試與商業化部署。


import React from "react";
import { createRoot } from "react-dom/client";
import { Activity, Map, Plane, Train, Route, Smartphone } from "lucide-react";
import "./styles.css";

type HealthState = "checking" | "ok" | "error";

function App() {
  const [health, setHealth] = React.useState<HealthState>("checking");

  React.useEffect(() => {
    fetch("/api/health")
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => setHealth(data.status === "ok" ? "ok" : "error"))
      .catch(() => setHealth("error"));
  }, []);

  const statusText = {
    checking: "检查中",
    ok: "后端在线",
    error: "后端不可用"
  }[health];

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Map size={28} />
          <div>
            <h1>SEMAP</h1>
            <p>移动轨迹记录与地图展示</p>
          </div>
        </div>

        <nav className="nav">
          <button className="navItem active"><Route size={18} />轨迹</button>
          <button className="navItem"><Plane size={18} />航班</button>
          <button className="navItem"><Train size={18} />火车</button>
          <button className="navItem"><Smartphone size={18} />定位</button>
        </nav>

        <div className={`status ${health}`}>
          <Activity size={18} />
          <span>{statusText}</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="toolbar">
          <div>
            <h2>轨迹地图</h2>
            <p>Web 前端已连接同源 API，后续接入登录、轨迹列表和 Google Maps。</p>
          </div>
          <div className="actions">
            <button>新增轨迹</button>
            <button>导入航班</button>
            <button>导入车次</button>
          </div>
        </header>

        <div className="contentGrid">
          <section className="mapSurface">
            <div className="mapPlaceholder">
              <Map size={42} />
              <span>Google Maps 展示区域</span>
            </div>
          </section>

          <section className="panel">
            <h3>交付范围</h3>
            <ul>
              <li>账号登录和用户轨迹隔离</li>
              <li>轨迹列表、地图绘制和选中高亮</li>
              <li>航班号和火车车次号导入</li>
              <li>轨迹详情编辑和删除</li>
            </ul>
          </section>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);

import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  CalendarClock,
  LogOut,
  Map,
  Plane,
  RefreshCw,
  Route,
  Train,
  User,
} from "lucide-react";
import {
  fetchHealth,
  fetchMe,
  fetchSegments,
  importFlight,
  importTrain,
  login,
  register,
} from "./api";
import { TrackMap } from "./TrackMap";
import type { Account, AuthMode, HealthState, TrackSegment, WorkspaceView } from "./types";
import "./styles.css";

const TOKEN_STORAGE_KEY = "semap.accessToken";
const CHINA_TIME_ZONE = "Asia/Shanghai";

const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  timeZone: CHINA_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const dateFormatter = new Intl.DateTimeFormat("zh-CN", {
  timeZone: CHINA_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function sourceLabel(sourceType: TrackSegment["sourceType"]) {
  return {
    flight: "航班",
    train: "火车",
    gps: "GPS",
  }[sourceType];
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "未设置";
  }
  const date = new Date(value);
  const parts = Object.fromEntries(dateTimeFormatter.formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}/${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
}

function formatDate(value: string | null) {
  if (!value) {
    return "未设置";
  }
  const date = new Date(value);
  const parts = Object.fromEntries(dateFormatter.formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}/${parts.month}/${parts.day}`;
}

function App() {
  const [health, setHealth] = React.useState<HealthState>("checking");
  const [token, setToken] = React.useState(() => localStorage.getItem(TOKEN_STORAGE_KEY) ?? "");
  const [account, setAccount] = React.useState<Account | null>(null);
  const [authMode, setAuthMode] = React.useState<AuthMode>("login");
  const [authError, setAuthError] = React.useState("");
  const [authBusy, setAuthBusy] = React.useState(false);
  const [booting, setBooting] = React.useState(Boolean(token));
  const [view, setView] = React.useState<WorkspaceView>("tracks");
  const [segments, setSegments] = React.useState<TrackSegment[]>([]);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [segmentsBusy, setSegmentsBusy] = React.useState(false);
  const [segmentsError, setSegmentsError] = React.useState("");

  const selectedSegment = React.useMemo(
    () => segments.find((segment) => segment.id === selectedId) ?? null,
    [segments, selectedId],
  );

  React.useEffect(() => {
    fetchHealth()
      .then((data) => setHealth(data.status === "ok" ? "ok" : "error"))
      .catch(() => setHealth("error"));
  }, []);

  React.useEffect(() => {
    if (!token) {
      setBooting(false);
      return;
    }

    fetchMe(token)
      .then((nextAccount) => setAccount(nextAccount))
      .catch(() => {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setToken("");
      })
      .finally(() => setBooting(false));
  }, [token]);

  const loadSegments = React.useCallback(() => {
    if (!token || !account) {
      return;
    }
    setSegmentsBusy(true);
    setSegmentsError("");
    fetchSegments(token)
      .then((nextSegments) => {
        setSegments(nextSegments);
        setSelectedId((currentId) => {
          if (nextSegments.some((segment) => segment.id === currentId)) {
            return currentId;
          }
          return null;
        });
      })
      .catch((error: Error) => setSegmentsError(error.message))
      .finally(() => setSegmentsBusy(false));
  }, [account, token]);

  React.useEffect(() => {
    loadSegments();
  }, [loadSegments]);

  function handleAuth(nextToken: string, nextAccount: Account) {
    localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
    setToken(nextToken);
    setAccount(nextAccount);
    setAuthError("");
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken("");
    setAccount(null);
    setSegments([]);
    setSelectedId(null);
  }

  if (booting) {
    return <LoadingScreen health={health} />;
  }

  if (!account) {
    return (
      <AuthScreen
        authMode={authMode}
        busy={authBusy}
        error={authError}
        health={health}
        onModeChange={setAuthMode}
        onSubmit={async (username, password) => {
          setAuthBusy(true);
          setAuthError("");
          try {
            if (authMode === "register") {
              await register(username, password);
            }
            const result = await login(username, password);
            handleAuth(result.accessToken, result.account);
          } catch (error) {
            setAuthError(error instanceof Error ? error.message : "请求失败");
          } finally {
            setAuthBusy(false);
          }
        }}
      />
    );
  }

  return (
    <Workspace
      account={account}
      health={health}
      view={view}
      segments={segments}
      selectedSegment={selectedSegment}
      segmentsBusy={segmentsBusy}
      segmentsError={segmentsError}
      token={token}
      onLogout={logout}
      onRefresh={loadSegments}
      onSelectSegment={setSelectedId}
      onSegmentsChange={setSegments}
      onViewChange={setView}
    />
  );
}

function LoadingScreen({ health }: { health: HealthState }) {
  return (
    <main className="authShell">
      <section className="authPanel compact">
        <BrandBlock />
        <HealthPill health={health} />
      </section>
    </main>
  );
}

function AuthScreen({
  authMode,
  busy,
  error,
  health,
  onModeChange,
  onSubmit,
}: {
  authMode: AuthMode;
  busy: boolean;
  error: string;
  health: HealthState;
  onModeChange: (mode: AuthMode) => void;
  onSubmit: (username: string, password: string) => void;
}) {
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");

  return (
    <main className="authShell">
      <section className="authPanel">
        <BrandBlock />

        <div className="segmented">
          <button
            className={authMode === "login" ? "active" : ""}
            onClick={() => onModeChange("login")}
            type="button"
          >
            登录
          </button>
          <button
            className={authMode === "register" ? "active" : ""}
            onClick={() => onModeChange("register")}
            type="button"
          >
            注册
          </button>
        </div>

        <form
          className="authForm"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit(username, password);
          }}
        >
          <label>
            <span>用户名</span>
            <input
              autoComplete="username"
              minLength={3}
              maxLength={64}
              onChange={(event) => setUsername(event.target.value)}
              required
              value={username}
            />
          </label>
          <label>
            <span>密码</span>
            <input
              autoComplete={authMode === "login" ? "current-password" : "new-password"}
              minLength={8}
              maxLength={128}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {error ? <p className="formError">{error}</p> : null}
          <button className="primaryButton" disabled={busy} type="submit">
            {busy ? "提交中" : authMode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>

        <HealthPill health={health} />
      </section>
    </main>
  );
}

function BrandBlock() {
  return (
    <div className="brandBlock">
      <div className="brandMark">
        <Map size={28} />
      </div>
      <div>
        <h1>SEMAP</h1>
        <p>移动轨迹记录与地图展示</p>
      </div>
    </div>
  );
}

function HealthPill({ health }: { health: HealthState }) {
  const statusText = {
    checking: "检查中",
    ok: "后端在线",
    error: "后端不可用",
  }[health];

  return (
    <div className={`healthPill ${health}`}>
      <Activity size={16} />
      <span>{statusText}</span>
    </div>
  );
}

function Workspace({
  account,
  health,
  view,
  segments,
  selectedSegment,
  segmentsBusy,
  segmentsError,
  token,
  onLogout,
  onRefresh,
  onSelectSegment,
  onSegmentsChange,
  onViewChange,
}: {
  account: Account;
  health: HealthState;
  view: WorkspaceView;
  segments: TrackSegment[];
  selectedSegment: TrackSegment | null;
  segmentsBusy: boolean;
  segmentsError: string;
  token: string;
  onLogout: () => void;
  onRefresh: () => void;
  onSelectSegment: (segmentId: number | null) => void;
  onSegmentsChange: (segments: TrackSegment[]) => void;
  onViewChange: (view: WorkspaceView) => void;
}) {
  return (
    <main
      className="shell"
      onPointerDown={(event) => {
        const target = event.target as Element;
        if (!target.closest(".trackList, .mapSurface")) {
          onSelectSegment(null);
        }
      }}
    >
      <aside className="sidebar">
        <BrandBlock />

        <nav className="nav">
          <button
            className={view === "tracks" ? "navItem active" : "navItem"}
            onClick={() => onViewChange("tracks")}
            type="button"
          >
            <Route size={18} />
            轨迹
          </button>
          <button
            className={view === "flight" ? "navItem active" : "navItem"}
            onClick={() => onViewChange("flight")}
            type="button"
          >
            <Plane size={18} />
            航班
          </button>
          <button
            className={view === "train" ? "navItem active" : "navItem"}
            onClick={() => onViewChange("train")}
            type="button"
          >
            <Train size={18} />
            火车
          </button>
        </nav>

        <div className="sidebarFooter">
          <HealthPill health={health} />
          <div className="accountBadge">
            <User size={16} />
            <span>{account.username}</span>
          </div>
          <button className="ghostButton" onClick={onLogout} type="button">
            <LogOut size={16} />
            退出
          </button>
        </div>
      </aside>

      <section className="workspace">
        <header className="toolbar">
          <div>
            <h2>{view === "tracks" ? "轨迹地图" : view === "flight" ? "航班导入" : "火车导入"}</h2>
            <p>{segments.length} 条轨迹</p>
          </div>
          <button className="secondaryButton" onClick={onRefresh} type="button">
            <RefreshCw size={16} />
            刷新
          </button>
        </header>

        {view === "tracks" ? (
          <TrackWorkspace
            segments={segments}
            selectedSegment={selectedSegment}
            busy={segmentsBusy}
            error={segmentsError}
            onSelectSegment={onSelectSegment}
          />
        ) : (
          <ImportPanel
            source={view}
            token={token}
            onImported={(segment) => {
              onSegmentsChange([segment, ...segments.filter((item) => item.id !== segment.id)]);
              onSelectSegment(segment.id);
              onViewChange("tracks");
            }}
          />
        )}
      </section>
    </main>
  );
}

function TrackWorkspace({
  segments,
  selectedSegment,
  busy,
  error,
  onSelectSegment,
}: {
  segments: TrackSegment[];
  selectedSegment: TrackSegment | null;
  busy: boolean;
  error: string;
  onSelectSegment: (segmentId: number | null) => void;
}) {
  return (
    <div className="contentGrid">
      <section className="mapSurface">
        <TrackMap
          segments={segments}
          selectedSegment={selectedSegment}
          onSelectSegment={onSelectSegment}
        />
      </section>

      <section className="sidePanel">
        <TrackList
          busy={busy}
          error={error}
          segments={segments}
          selectedSegment={selectedSegment}
          onSelectSegment={onSelectSegment}
        />
      </section>
    </div>
  );
}

function TrackList({
  busy,
  error,
  segments,
  selectedSegment,
  onSelectSegment,
}: {
  busy: boolean;
  error: string;
  segments: TrackSegment[];
  selectedSegment: TrackSegment | null;
  onSelectSegment: (segmentId: number | null) => void;
}) {
  return (
    <div className="panelSection">
      <div className="panelHeader">
        <h3>轨迹列表</h3>
        {busy ? <span>同步中</span> : null}
      </div>
      {error ? <p className="formError">{error}</p> : null}
      {segments.length === 0 && !busy ? <p className="emptyText">暂无轨迹</p> : null}
      <div className="trackList">
        {segments.map((segment) => (
          <button
            className={selectedSegment?.id === segment.id ? "trackItem active" : "trackItem"}
            key={segment.id}
            onClick={(event) => {
              event.stopPropagation();
              onSelectSegment(segment.id);
            }}
            type="button"
          >
            <div className="trackItemTitle">
              <TrackLogo segment={segment} />
              <div className="trackItemText">
                <span className="trackType">{sourceLabel(segment.sourceType)}</span>
                <strong>{segment.title}</strong>
                <span className="trackDate">{formatDate(segment.startedAt)}</span>
              </div>
            </div>
            {selectedSegment?.id === segment.id ? (
              <>
                <SegmentMetadata segment={segment} compact />
              </>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}

function TrackLogo({ segment }: { segment: TrackSegment }) {
  const metadata = segment.metadata ?? {};
  const text = metadata.logoText ?? metadata.operatorCode ?? sourceLabel(segment.sourceType);
  const logoUrl = metadata.logoKind === "railway_12306" ? "/logos/China_Railways.svg" : metadata.logoUrl;
  if (logoUrl) {
    return (
      <span
        className={
          metadata.logoKind === "railway_12306"
            ? "trackLogo imageLogo railway12306Logo"
            : "trackLogo imageLogo"
        }
      >
        <img
          alt=""
          onError={(event) => {
            event.currentTarget.removeAttribute("src");
          }}
          src={logoUrl}
        />
        <span>{text.slice(0, 3)}</span>
      </span>
    );
  }
  return (
    <span
      className={metadata.logoKind === "railway_12306" ? "trackLogo railway12306Logo" : "trackLogo"}
    >
      {text.slice(0, 5)}
    </span>
  );
}

function trainStationName(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  return value.endsWith("站") ? value : `${value}站`;
}

function segmentStartPlace(segment: TrackSegment) {
  if (segment.sourceType === "train") {
    return trainStationName(segment.points[0]?.name);
  }
  return segment.metadata?.originLocation ?? segment.points[0]?.name ?? null;
}

function segmentEndPlace(segment: TrackSegment) {
  if (segment.sourceType === "train") {
    return trainStationName(segment.points.at(-1)?.name);
  }
  return segment.metadata?.destinationLocation ?? segment.points.at(-1)?.name ?? null;
}

function SegmentMetadata({
  segment,
  compact = false,
}: {
  segment: TrackSegment;
  compact?: boolean;
}) {
  const metadata = segment.metadata ?? {};
  const startPlace = segmentStartPlace(segment);
  const endPlace = segmentEndPlace(segment);
  const primaryItems = [
    metadata.operatorName ? ["运营方", metadata.operatorName] : null,
    metadata.vehicleModel ? [segment.sourceType === "train" ? "担当车型" : "机型", metadata.vehicleModel] : null,
    metadata.registration ? ["注册号", metadata.registration] : null,
  ].filter(Boolean) as [string, string][];
  const locationItems = [
    startPlace ? [segment.sourceType === "train" ? "出发地点" : "起飞地点", startPlace] : null,
    endPlace ? [segment.sourceType === "train" ? "到达地点" : "降落地点", endPlace] : null,
  ].filter(Boolean) as [string, string][];
  const timeItems = [
    ["出发时间", formatDateTime(segment.startedAt)],
    ["到达时间", formatDateTime(segment.endedAt)],
  ].filter(Boolean) as [string, string][];
  const extraItems = [
    metadata.unitNo && !compact ? ["车组号", metadata.unitNo] : null,
  ].filter(Boolean) as [string, string][];

  if (primaryItems.length === 0 && locationItems.length === 0 && timeItems.length === 0 && extraItems.length === 0) {
    return null;
  }

  return (
    <div className={compact ? "metadataLine compact" : "metadataLine"}>
      {primaryItems.length ? (
        <div className="metadataGroup">
          {primaryItems.map(([label, value]) => (
            <span key={label}>
              {label}：{value}
            </span>
          ))}
        </div>
      ) : null}
      {locationItems.map(([label, value]) => (
        <span className="metadataRow" key={label}>
          {label}：{value}
        </span>
      ))}
      {timeItems.map(([label, value]) => (
        <span className="metadataRow" key={label}>
          {label}：{value}
        </span>
      ))}
      {extraItems.map(([label, value]) => (
        <span className="metadataRow" key={label}>
          {label}：{value}
        </span>
      ))}
    </div>
  );
}

function ImportPanel({
  source,
  token,
  onImported,
}: {
  source: "flight" | "train";
  token: string;
  onImported: (segment: TrackSegment) => void;
}) {
  const isFlight = source === "flight";
  const [code, setCode] = React.useState("");
  const [date, setDate] = React.useState(() => new Date().toISOString().slice(0, 10));
  const [fromStation, setFromStation] = React.useState("");
  const [toStation, setToStation] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    setCode("");
    setFromStation("");
    setToStation("");
    setError("");
  }, [source]);

  return (
    <section className="importSurface">
      <div className="importHeader">
        {isFlight ? <Plane size={24} /> : <Train size={24} />}
        <div>
          <h3>{isFlight ? "航班号导入" : "车次号导入"}</h3>
          <p>{isFlight ? "FlightRadar24" : "12306 指定日期"}</p>
        </div>
      </div>
      <form
        className="importForm"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          try {
            const segment = isFlight
              ? await importFlight(token, {
                  flightNumber: code,
                  date,
                })
              : await importTrain(token, {
                  trainCode: code,
                  date,
                  fromStation,
                  toStation,
                });
            onImported(segment);
          } catch (importError) {
            setError(importError instanceof Error ? importError.message : "导入失败");
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          <span>{isFlight ? "航班号" : "车次号"}</span>
          <input
            placeholder={isFlight ? "UA938" : "G803"}
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            required
          />
        </label>
        <label>
          <span>日期</span>
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
        </label>
        {!isFlight ? (
          <div className="fieldGrid">
            <label>
              <span>乘车起点</span>
              <input
                placeholder="北京南"
                value={fromStation}
                onChange={(event) => setFromStation(event.target.value)}
                required
              />
            </label>
            <label>
              <span>乘车终点</span>
              <input
                placeholder="上海虹桥"
                value={toStation}
                onChange={(event) => setToStation(event.target.value)}
                required
              />
            </label>
          </div>
        ) : null}
        {error ? <p className="formError">{error}</p> : null}
        <button className="primaryButton" disabled={busy} type="submit">
          <CalendarClock size={16} />
          {busy ? "导入中" : "导入轨迹"}
        </button>
      </form>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(<App />);

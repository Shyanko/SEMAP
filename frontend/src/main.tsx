import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  CalendarClock,
  Download,
  LogOut,
  Pencil,
  Plane,
  RefreshCw,
  Route,
  Trash2,
  Train,
  User,
  X,
} from "lucide-react";
import {
  deleteSegment,
  fetchHealth,
  fetchMe,
  fetchSegments,
  fetchTrainStations,
  importFlight,
  importTrain,
  login,
  register,
  updateSegment,
} from "./api";
import { TrackMap } from "./TrackMap";
import type { Account, AuthMode, HealthState, TrackSegment, TrainStationsResponse, WorkspaceView } from "./types";
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

function toDateTimeLocal(value: string | null) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  const parts = Object.fromEntries(dateTimeFormatter.formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

function fromDateTimeLocal(value: string) {
  return value ? `${value}:00+08:00` : null;
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
        <ApkDownloadLink />
      </section>
    </main>
  );
}

function BrandBlock() {
  return (
    <div className="brandBlock">
      <div className="brandMark">
        <img alt="" src="/logos/semap-logo.png" />
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
  const [editingSegment, setEditingSegment] = React.useState<TrackSegment | null>(null);

  return (
    <main
      className={view === "tracks" ? "shell tracksShell" : "shell importShell"}
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
            轨迹地图
          </button>
          <button
            className={view === "flight" ? "navItem active" : "navItem"}
            onClick={() => onViewChange("flight")}
            type="button"
          >
            <Plane size={18} />
            航班导入
          </button>
          <button
            className={view === "train" ? "navItem active" : "navItem"}
            onClick={() => onViewChange("train")}
            type="button"
          >
            <Train size={18} />
            火车导入
          </button>
        </nav>

        <div className="sidebarFooter">
          <HealthPill health={health} />
          <ApkDownloadLink />
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
            onEditSegment={setEditingSegment}
          />
        ) : (
          <div className="importStage">
            <ImportPanel
              source={view}
              token={token}
              onImported={(segment) => {
                onSegmentsChange([segment, ...segments.filter((item) => item.id !== segment.id)]);
                onSelectSegment(segment.id);
                onViewChange("tracks");
              }}
            />
          </div>
        )}
      </section>
      {editingSegment ? (
        <SegmentEditDialog
          segment={editingSegment}
          token={token}
          onClose={() => setEditingSegment(null)}
          onDeleted={(segmentId) => {
            onSegmentsChange(segments.filter((segment) => segment.id !== segmentId));
            onSelectSegment(null);
            setEditingSegment(null);
          }}
          onSaved={(segment) => {
            onSegmentsChange(segments.map((item) => (item.id === segment.id ? segment : item)));
            onSelectSegment(segment.id);
            setEditingSegment(null);
          }}
        />
      ) : null}
    </main>
  );
}

function ApkDownloadLink() {
  return (
    <div className="downloadBlock">
      <a className="downloadButton" download href="/downloads/SEMAP-1.0.apk">
        <Download size={16} />
        下载 Android APK
      </a>
      <p>手机端支持定位上传功能</p>
    </div>
  );
}

function TrackWorkspace({
  segments,
  selectedSegment,
  busy,
  error,
  onSelectSegment,
  onEditSegment,
}: {
  segments: TrackSegment[];
  selectedSegment: TrackSegment | null;
  busy: boolean;
  error: string;
  onSelectSegment: (segmentId: number | null) => void;
  onEditSegment: (segment: TrackSegment) => void;
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
          onEditSegment={onEditSegment}
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
  onEditSegment,
  segments,
  selectedSegment,
  onSelectSegment,
}: {
  busy: boolean;
  error: string;
  onEditSegment: (segment: TrackSegment) => void;
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
          <div
            className={selectedSegment?.id === segment.id ? "trackItem active" : "trackItem"}
            key={segment.id}
            onClick={(event) => {
              event.stopPropagation();
              onSelectSegment(segment.id);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectSegment(segment.id);
              }
            }}
            role="button"
            tabIndex={0}
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
                <div className="trackCardFooter">
                  <button
                    className="secondaryButton compactButton"
                    onClick={(event) => {
                      event.stopPropagation();
                      onEditSegment(segment);
                    }}
                    type="button"
                  >
                    <Pencil size={15} />
                    更改
                  </button>
                </div>
              </>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function TrackLogo({ segment }: { segment: TrackSegment }) {
  const metadata = segment.metadata ?? {};
  const text = metadata.logoText ?? metadata.operatorCode ?? sourceLabel(segment.sourceType);
  const logoUrl =
    metadata.logoKind === "railway_12306"
      ? "/logos/China_Railways.svg"
      : segment.sourceType === "gps"
        ? "/logos/road.png"
        : metadata.logoUrl;
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

function SegmentEditDialog({
  segment,
  token,
  onClose,
  onDeleted,
  onSaved,
}: {
  segment: TrackSegment;
  token: string;
  onClose: () => void;
  onDeleted: (segmentId: number) => void;
  onSaved: (segment: TrackSegment) => void;
}) {
  const [title, setTitle] = React.useState(segment.title);
  const [startedAt, setStartedAt] = React.useState(() => toDateTimeLocal(segment.startedAt));
  const [endedAt, setEndedAt] = React.useState(() => toDateTimeLocal(segment.endedAt));
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    setTitle(segment.title);
    setStartedAt(toDateTimeLocal(segment.startedAt));
    setEndedAt(toDateTimeLocal(segment.endedAt));
    setError("");
  }, [segment]);

  return (
    <div className="modalBackdrop" onPointerDown={onClose}>
      <section
        aria-modal="true"
        className="editModal"
        onPointerDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="modalHeader">
          <div>
            <h3>更改路径</h3>
            <p>{sourceLabel(segment.sourceType)} · v{segment.version}</p>
          </div>
          <button className="iconButton" onClick={onClose} type="button">
            <X size={18} />
          </button>
        </div>
        <form
          className="editForm"
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setError("");
            try {
              const saved = await updateSegment(token, segment.id, {
                version: segment.version,
                title,
                startedAt: fromDateTimeLocal(startedAt),
                endedAt: fromDateTimeLocal(endedAt),
              });
              onSaved(saved);
            } catch (updateError) {
              setError(updateError instanceof Error ? updateError.message : "保存失败");
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            <span>标题</span>
            <input
              maxLength={200}
              minLength={1}
              onChange={(event) => setTitle(event.target.value)}
              required
              value={title}
            />
          </label>
          <label>
            <span>出发时间</span>
            <input
              onChange={(event) => setStartedAt(event.target.value)}
              type="datetime-local"
              value={startedAt}
            />
          </label>
          <label>
            <span>到达时间</span>
            <input
              onChange={(event) => setEndedAt(event.target.value)}
              type="datetime-local"
              value={endedAt}
            />
          </label>
          {error ? <p className="formError">{error}</p> : null}
          <div className="modalActions">
            <button
              className="dangerButton"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await deleteSegment(token, segment.id, segment.version);
                  onDeleted(segment.id);
                } catch (deleteError) {
                  setError(deleteError instanceof Error ? deleteError.message : "删除失败");
                } finally {
                  setBusy(false);
                }
              }}
              type="button"
            >
              <Trash2 size={16} />
              删除路径
            </button>
            <button className="primaryButton" disabled={busy} type="submit">
              {busy ? "处理中" : "保存"}
            </button>
          </div>
        </form>
      </section>
    </div>
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
  const primaryItems = segmentPrimaryMetadata(segment);
  const locationItems = [
    startPlace ? [segment.sourceType === "train" ? "出发地点" : "起飞地点", startPlace] : null,
    endPlace ? [segment.sourceType === "train" ? "到达地点" : "降落地点", endPlace] : null,
  ].filter(Boolean) as [string, string][];
  const timeItems = [
    ["出发时间", formatDateTime(segment.startedAt)],
    ["到达时间", formatDateTime(segment.endedAt)],
  ].filter(Boolean) as [string, string][];

  if (primaryItems.length === 0 && locationItems.length === 0 && timeItems.length === 0) {
    return null;
  }

  return (
    <div className={compact ? "metadataLine compact" : "metadataLine"}>
      {primaryItems.map(([label, value]) => (
        <span className="metadataRow" key={label}>
          {label}：{value}
        </span>
      ))}
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
    </div>
  );
}

function segmentPrimaryMetadata(segment: TrackSegment): [string, string][] {
  const metadata = segment.metadata ?? {};
  if (segment.sourceType === "flight") {
    const aircraftItem =
      metadata.vehicleModel && metadata.registration
        ? ["机型", `${metadata.vehicleModel}　注册号：${metadata.registration}`]
        : metadata.vehicleModel
          ? ["机型", metadata.vehicleModel]
          : metadata.registration
            ? ["注册号", metadata.registration]
            : null;
    return [
      segment.externalCode ? ["航班号", segment.externalCode] : null,
      metadata.operatorName ? ["运营方", metadata.operatorName] : null,
      aircraftItem,
    ].filter(Boolean) as [string, string][];
  }
  if (segment.sourceType === "train") {
    const trainCode = segment.externalCode;
    const vehicleModel = metadata.vehicleModel;
    if (trainCode && vehicleModel) {
      return [["车次", `${trainCode}　担当车型：${vehicleModel}`]];
    }
    if (trainCode) {
      return [["车次", trainCode]];
    }
    if (vehicleModel) {
      return [["担当车型", vehicleModel]];
    }
  }
  return [];
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
  const [date, setDate] = React.useState("");
  const [fromStation, setFromStation] = React.useState("");
  const [toStation, setToStation] = React.useState("");
  const [trainStations, setTrainStations] = React.useState<TrainStationsResponse | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const stationOptions =
    !isFlight && trainStations?.trainCode === code && trainStations.requestedDate === date
      ? trainStations.stations
      : [];
  const fromIndex = stationOptions.findIndex((station) => station.name === fromStation);
  const toOptions = fromIndex >= 0 ? stationOptions.slice(fromIndex + 1) : [];

  React.useEffect(() => {
    setCode("");
    setFromStation("");
    setToStation("");
    setTrainStations(null);
    setError("");
  }, [source]);

  return (
    <section className="importSurface">
      <div className="importHeader">
        {isFlight ? <Plane size={24} /> : <Train size={24} />}
        <div>
          <h3>{isFlight ? "航班号导入" : "车次号导入"}</h3>
        </div>
      </div>
      <form
        className="importForm"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          try {
            if (!isFlight && stationOptions.length === 0) {
              const nextStations = await fetchTrainStations(token, {
                trainCode: code,
                date,
              });
              setTrainStations(nextStations);
              setFromStation("");
              setToStation("");
              return;
            }
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
            value={code}
            onChange={(event) => {
              setCode(event.target.value.toUpperCase());
              setFromStation("");
              setToStation("");
              setTrainStations(null);
            }}
            required
          />
        </label>
        <label>
          <span>日期</span>
          <input
            type="date"
            value={date}
            onChange={(event) => {
              setDate(event.target.value);
              setFromStation("");
              setToStation("");
              setTrainStations(null);
            }}
            required
          />
        </label>
        {!isFlight && stationOptions.length > 0 ? (
          <>
            <div className="stationList">
              {stationOptions.map((station) => (
                <span className="stationChip" key={`${station.sequence}-${station.name}`}>
                  <strong>{station.name}</strong>
                  <span>{station.startTime && station.startTime !== "----" ? station.startTime : station.arriveTime}</span>
                </span>
              ))}
            </div>
            <div className="fieldGrid">
              <label>
                <span>乘车起点</span>
                <select
                  value={fromStation}
                  onChange={(event) => {
                    setFromStation(event.target.value);
                    setToStation("");
                  }}
                  required
                >
                  <option value="">选择出发站</option>
                  {stationOptions.slice(0, -1).map((station) => (
                    <option key={station.sequence} value={station.name}>
                      {station.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>乘车终点</span>
                <select
                  disabled={!fromStation}
                  value={toStation}
                  onChange={(event) => setToStation(event.target.value)}
                  required
                >
                  <option value="">选择到达站</option>
                  {toOptions.map((station) => (
                    <option key={station.sequence} value={station.name}>
                      {station.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </>
        ) : null}
        {error ? <p className="formError">{error}</p> : null}
        <button
          className="primaryButton"
          disabled={
            busy ||
            !code ||
            !date ||
            (!isFlight && stationOptions.length > 0 && (!fromStation || !toStation))
          }
          type="submit"
        >
          <CalendarClock size={16} />
          {busy ? (isFlight || stationOptions.length > 0 ? "导入中" : "查询中") : isFlight || stationOptions.length > 0 ? "导入轨迹" : "查询站点"}
        </button>
      </form>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(<App />);

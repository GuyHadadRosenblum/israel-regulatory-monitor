import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUpLeft,
  Check,
  ChevronLeft,
  Download,
  FileText,
  GitBranch,
  LayoutDashboard,
  Play,
  Search,
  Settings2,
  ShieldCheck,
  Upload,
  X,
  Clock,
  Info,
  ExternalLink,
} from "lucide-react";
import {
  Regulation,
  labels,
  riaLabels,
  filterRows,
  csv,
  similarity,
} from "./model";
import { demoRows, steps } from "./demo";

const repo = "https://github.com/GuyHadadRosenblum/israel-regulatory-monitor";
const STATIC = import.meta.env.VITE_DEMO_ONLY === "true";
function download(blob: Blob, name: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
async function api(path: string, options?: RequestInit) {
  const r = await fetch("/api" + path, options);
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "לא ניתן להתחבר לשרת" }));
    throw Error(
      typeof e.detail === "string" ? e.detail : "בדקו את הנתונים שהוזנו",
    );
  }
  return r;
}

export default function App() {
  const [view, setView] = useState("overview"),
    [rows, setRows] = useState<Regulation[]>(demoRows),
    [mode, setMode] = useState<"demo" | "local">("demo"),
    [local, setLocal] = useState(false),
    [query, setQuery] = useState(""),
    [status, setStatus] = useState("all"),
    [ministry, setMinistry] = useState("all"),
    [selected, setSelected] = useState<Regulation | null>(null),
    [stage, setStage] = useState(-1),
    [running, setRunning] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [since, setSince] = useState(
      new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10),
    ),
    [job, setJob] = useState("");
  const [a, setA] = useState(
      "תקנות בטיחות באתרי בנייה מחייבות בדיקה תקופתית ותיעוד הדרכת עובדים",
    ),
    [b, setB] = useState(
      "תקנות בטיחות באתרי בנייה מחייבות בדיקה תקופתית ותיעוד הדרכת עובדים הוראות מעבר",
    );
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!STATIC)
      api("/health")
        .then(() => setLocal(true))
        .catch(() => {});
  }, []);
  useEffect(() => {
    if (selected) dialog.current?.showModal();
    else dialog.current?.close();
  }, [selected]);
  useEffect(() => {
    if (!running || mode !== "demo") return;
    const t = setInterval(() => setStage((s) => s + 1), 650);
    return () => clearInterval(t);
  }, [running, mode]);
  useEffect(() => {
    if (stage >= 5 && mode === "demo") {
      setRunning(false);
      setRows(demoRows.map((r) => ({ ...r })));
      setMessage(
        "ההדגמה הושלמה. 10 רשומות זמינות לבדיקה; לא בוצעה פנייה למקורות חיצוניים.",
      );
    }
  }, [stage, mode]);
  useEffect(() => {
    if (!job || !running) return;
    const tick = async () => {
      try {
        const j = await (await api("/runs/" + job)).json();
        setStage(j.stage);
        if (j.status === "completed") {
          setRows(await (await api("/regulations")).json());
          setRunning(false);
          setMessage("הניטור הושלם והתוצאות עודכנו.");
        } else if (j.status === "failed") {
          setRunning(false);
          setError(j.error);
        }
      } catch (e) {
        setRunning(false);
        setError(String(e));
      }
    };
    const t = setInterval(tick, 1500);
    return () => clearInterval(t);
  }, [job, running]);
  async function changeMode(value: "demo" | "local") {
    setMode(value);
    setError("");
    setMessage("");
    setStage(-1);
    setStatus("all");
    setMinistry("all");
    setQuery("");
    if (value === "demo") setRows(demoRows);
    else
      try {
        setRows(await (await api("/regulations")).json());
      } catch (e) {
        setRows([]);
        setError(String(e));
      }
  }
  async function run() {
    setError("");
    setMessage("");
    setStage(0);
    if (mode === "demo") {
      setRunning(true);
      return;
    }
    try {
      const j = await (
        await api("/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ since }),
        })
      ).json();
      setJob(j.id);
      setRunning(true);
    } catch (e) {
      setError(String(e));
      setStage(-1);
    }
  }
  async function exportRows() {
    try {
      if (mode === "local")
        download(
          await (await api("/export")).blob(),
          "regulatory-monitor.xlsx",
        );
      else
        download(
          new Blob([csv(visible)], { type: "text/csv;charset=utf-8" }),
          "regulatory-demo.csv",
        );
    } catch (e) {
      setError(String(e));
    }
  }
  async function upload(file?: File) {
    if (!file) return;
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await api("/monday", { method: "POST", body: form });
      download(await r.blob(), "monday-tracking.xlsx");
      setMessage("טבלת המעקב הופקה וירדה למחשב.");
    } catch (e) {
      setError(String(e));
    }
  }
  const visible = filterRows(rows, query, status, ministry),
    counts = {
      matched: rows.filter((r) => r.status === "matched").length,
      missing: rows.filter((r) => r.status === "missing").length,
      review: rows.filter(
        (r) => r.status === "review" || r.status === "submission",
      ).length,
    };
  const nav = [
    ["overview", "תמונת מצב", LayoutDashboard],
    ["monitor", "ניטור והצלבה", Activity],
    ["reports", "דוחות ותוצרים", FileText],
    ["about", "על הפרויקט", GitBranch],
  ] as const;
  function openMonitor(nextStatus = "all") {
    setStatus(nextStatus);
    setQuery("");
    setMinistry("all");
    setView("monitor");
  }
  return (
    <div className="shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("overview");
          }}
        >
          <span className="brand-mark">
            <Activity size={25} />
          </span>
          <span>
            אסדרה<small>מערכת ניטור ובקרה</small>
          </span>
        </a>
        <div className="workspace-label">סביבת עבודה</div>
        <nav aria-label="ניווט ראשי">
          {nav.map(([id, text, Icon]) => (
            <button
              key={id}
              className={view === id ? "nav-item active" : "nav-item"}
              onClick={() => setView(id)}
            >
              <Icon size={19} />
              {text}
              {view === id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="system-line">
            <span className="online-dot" />
            {mode === "demo" ? "סביבת הדגמה" : "סביבה מקומית"}
          </div>
          <p>מפרסום חדש לתמונת מצב ברורה.</p>
          <a href={repo} target="_blank" rel="noreferrer">
            <GitBranch size={16} /> הקוד ב־GitHub <ArrowUpLeft size={15} />
          </a>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="breadcrumb">
            ניטור רגולציה <ChevronLeft size={14} />
            <strong>{nav.find((n) => n[0] === view)?.[1]}</strong>
          </div>
          <div className="topbar-tools">
            <span className="mode-tag">
              {mode === "demo" ? "הדגמה אינטראקטיבית" : "נתונים מקומיים"}
            </span>
            <span className="avatar">GH</span>
          </div>
        </header>
        <main id="main">
          <div className="demo-notice">
            <Info size={17} />
            <span>
              {mode === "demo"
                ? "נתוני הדגמה להמחשת תהליך העבודה. הנתונים אינם פרסומים אמיתיים או החלטות של הרשות."
                : "המערכת מציגה נתונים מההרצה המקומית שלך."}
            </span>
            {local && (
              <select
                aria-label="מצב הפעלה"
                value={mode}
                disabled={running}
                onChange={(e) => changeMode(e.target.value as "demo" | "local")}
              >
                <option value="demo">הדגמה</option>
                <option value="local">הפעלה אמיתית</option>
              </select>
            )}
          </div>
          {error && (
            <div className="notice error" role="alert">
              {error}
              <button aria-label="סגירת שגיאה" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {message && (
            <div className="notice success" role="status">
              {message}
            </div>
          )}
          {(view === "overview" || view === "monitor") && (
            <>
              <section className="page-heading">
                <div>
                  <h1>
                    {view === "overview"
                      ? "כל הרגולציה. תמונה אחת."
                      : "מפרסום לפנייה. בלי לפספס."}
                  </h1>
                  <p>{view === "overview" ? "סיכום המעקב והפערים שדורשים תשומת לב." : "הפעלת איסוף, בדיקת התאמות ועבודה עם מאגר הרגולציות."}</p>
                </div>
                {view === "overview" ? <button className="primary" onClick={() => openMonitor()}>מעבר לניטור והצלבה <ChevronLeft size={16} /></button> : <button className="primary" onClick={run} disabled={running}>
                  <Play size={16} />
                  {running
                    ? "הניטור מתבצע…"
                    : mode === "demo"
                      ? "הפעלת הדגמה"
                      : "הפעלת ניטור"}
                </button>}
              </section>
              {view === "overview" && <>
              <section className="metrics" aria-label="סיכום נתונים">
                <button
                  onClick={() => openMonitor()}
                  className="metric"
                >
                  <span>
                    רגולציות במעקב <FileText size={17} />
                  </span>
                  <strong>{rows.length.toString().padStart(2, "0")}</strong>
                  <small>מכל מקורות המידע</small>
                </button>
                <button onClick={() => openMonitor("matched")} className="metric">
                  <span>
                    פניות שהוצלבו <ShieldCheck size={17} />
                  </span>
                  <strong>{counts.matched.toString().padStart(2, "0")}</strong>
                  <small>
                    <i className="dot green" />
                    נמצאה התאמה בין המקורות
                  </small>
                </button>
                <button onClick={() => openMonitor("missing")} className="metric">
                  <span>
                    ללא פנייה רשמית <Info size={17} />
                  </span>
                  <strong>{counts.missing.toString().padStart(2, "0")}</strong>
                  <small>
                    <i className="dot amber" />
                    פרסום ללא פנייה תואמת
                  </small>
                </button>
                <button onClick={() => openMonitor("review")} className="metric">
                  <span>
                    התאמות לבדיקה <Search size={17} />
                  </span>
                  <strong>
                    {rows
                      .filter((r) => r.status === "review")
                      .length.toString()
                      .padStart(2, "0")}
                  </strong>
                  <small>נדרשת בדיקה אנושית</small>
                </button>
              </section>
              <section className="overview-brief" aria-label="סדר יום לבדיקה">
                <div className="brief-heading">
                  <h2>מה דורש תשומת לב?</h2>
                  <p>{counts.missing + counts.review} רשומות ללא התאמה מאומתת. בחרו קבוצה כדי לעבור לבדיקה ממוקדת.</p>
                </div>
                {(["missing", "review", "submission"] as const).map((kind) => {
                  const count = rows.filter((r) => r.status === kind).length;
                  return <button className="attention-row" key={kind} onClick={() => openMonitor(kind)}>
                    <strong>{count}</strong>
                    <span><b>{labels[kind]}</b><small>{kind === "missing" ? "פרסומים שלא אותרה עבורם פנייה תואמת" : kind === "review" ? "מסמכים שההתאמה ביניהם דורשת בדיקה אנושית" : "פניות שטרם נמצא עבורן פרסום תואם"}</small></span>
                    <ChevronLeft size={19} />
                  </button>;
                })}
                {!rows.length && <p className="inline-note">טרם הופק דוח. עברו לניטור והצלבה כדי להתחיל.</p>}
              </section>
              <div className="overview-note"><ShieldCheck size={22} /><p>תמונת המצב מסכמת את הנתונים הזמינים במערכת. איסוף חדש, סינון ופרטי מסמכים נמצאים בלשונית ניטור והצלבה.</p></div>
              </>}
              {view === "monitor" && <>
              <section className="pipeline">
                <div className="pipeline-head">
                  <div>
                    <Activity size={18} />
                    <strong>תהליך הניטור</strong>
                    <span>
                      {stage >= 5
                        ? "הושלם"
                        : running
                          ? "בתהליך"
                          : mode === "demo"
                            ? "הדגמת חמשת שלבי העבודה"
                            : "מוכן להפעלה"}
                    </span>
                  </div>
                  {mode === "local" && (
                    <label className="date-label">
                      פרסומים מתאריך{" "}
                      <input
                        type="date"
                        value={since}
                        onChange={(e) => setSince(e.target.value)}
                        disabled={running}
                      />
                    </label>
                  )}
                </div>
                <ol className="steps">
                  {steps.map((s, i) => (
                    <li
                      key={s}
                      className={
                        stage > i
                          ? "done"
                          : stage === i && running
                            ? "current"
                            : ""
                      }
                    >
                      <span className="step-number">
                        {stage > i ? <Check size={15} /> : i + 1}
                      </span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ol>
              </section>
              <section className="registry">
                <div className="section-heading">
                  <div>
                    <h2>מאגר הרגולציות</h2>
                    <span>{visible.length} רשומות</span>
                  </div>
                  <button
                    className="secondary"
                    onClick={exportRows}
                    disabled={!rows.length}
                  >
                    <Download size={16} />
                    ייצוא {mode === "demo" ? "CSV" : "Excel"}
                  </button>
                </div>
                <div className="filters">
                  <label className="search">
                    <Search size={17} />
                    <input
                      placeholder="חיפוש לפי נושא או משרד…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <select
                    aria-label="סינון משרד"
                    value={ministry}
                    onChange={(e) => setMinistry(e.target.value)}
                  >
                    <option value="all">כל המשרדים</option>
                    {[...new Set(rows.map((r) => r.ministry))].map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                  <select
                    aria-label="סינון סטטוס"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    <option value="all">כל הסטטוסים</option>
                    {Object.entries(labels).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                  <button
                    className="icon-button"
                    aria-label="איפוס סינון"
                    onClick={() => {
                      setQuery("");
                      setStatus("all");
                      setMinistry("all");
                    }}
                  >
                    <Settings2 size={18} />
                  </button>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>נושא הרגולציה</th>
                        <th>משרד אחראי</th>
                        <th>מועד פרסום</th>
                        <th>הצלבת פנייה</th>
                        <th>הערכת השפעות</th>
                        <th>
                          <span className="sr-only">פרטים</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {visible.map((r) => (
                        <tr key={r.id}>
                          <td>
                            <button
                              className="title-link"
                              onClick={() => setSelected(r)}
                            >
                              {r.title}
                            </button>
                          </td>
                          <td>{r.ministry}</td>
                          <td className="date">{r.date}</td>
                          <td>
                            <span className={"status " + r.status}>
                              <i />
                              {labels[r.status]}
                            </span>
                          </td>
                          <td>
                            <span className={"ria " + r.ria}>
                              {r.ria === "available" ? (
                                <FileText size={14} />
                              ) : r.ria === "exempt" ? (
                                <Check size={14} />
                              ) : (
                                <Clock size={14} />
                              )}{" "}
                              {riaLabels[r.ria]}
                            </span>
                          </td>
                          <td>
                            <button
                              className="icon-button"
                              aria-label={"פרטים: " + r.title}
                              onClick={() => setSelected(r)}
                            >
                              <ChevronLeft size={17} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!visible.length && (
                    <div className="empty">
                      <Search size={28} />
                      <h3>
                        {rows.length
                          ? "לא נמצאו רשומות מתאימות"
                          : "טרם הופק דוח ניטור"}
                      </h3>
                      <p>
                        {rows.length
                          ? "נסו לשנות את החיפוש או הסינון."
                          : "הגדירו הרשאות מקומיות והפעילו ניטור, או עברו להדגמה."}
                      </p>
                    </div>
                  )}
                </div>
                <div className="table-footer">
                  <span>
                    ההתאמה מבוססת על משרד, תאריך ודמיון בתוכן המסמכים.
                  </span>
                  <span>סיווג אוטומטי דורש בקרה אנושית</span>
                </div>
              </section>
              </>}
            </>
          )}
          {view === "reports" && (
            <>
              <section className="page-heading">
                <div>
                  <h1>מהנתונים לעבודה היומיומית.</h1>
                  <p>דוחות להורדה, טבלאות מעקב והעברת מידע להמשך טיפול.</p>
                </div>
              </section>
              <section className="report-layout">
                <article className="report-card">
                  <FileText size={32} />
                  <h2>דוח ניטור והצלבה</h2>
                  <p>רשימת הרגולציות עם המשרד האחראי, מצב ההתאמה וסטטוס RIA.</p>
                  <button className="primary" onClick={exportRows}>
                    <Download size={16} />
                    הורדת דוח {mode === "demo" ? "הדגמה" : "ניטור"}
                  </button>
                </article>
                <article className="report-card">
                  <Upload size={32} />
                  <h2>מעקב אחר פניות מ־Monday</h2>
                  <p>
                    העלאת ייצוא Excel עם כותרות בשורה השלישית. המערכת תחשב מועדי
                    יעד לפי 14 או 74 ימים ותפיק טבלה להורדה.
                  </p>
                  {mode === "local" ? (
                    <label className="upload-label">
                      בחירת קובץ Excel
                      <input
                        type="file"
                        accept=".xlsx"
                        onChange={(e) => upload(e.target.files?.[0])}
                      />
                    </label>
                  ) : (
                    <div className="inline-note">
                      עיבוד קובצי Monday זמין בהפעלה המקומית. הוראות ההפעלה
                      נמצאות ב־GitHub.
                    </div>
                  )}
                </article>
              </section>
              <div className="explanation">
                <h3>התוצרים המקוריים נשמרו</h3>
                <p>
                  סקריפטים להפקת גאנט וטבלת זרם היסטורית זמינים בקוד המקור. הם
                  מופעלים מקומית על קובצי העבודה של הארגון, לפי ההוראות במאגר.
                </p>
              </div>
            </>
          )}
          {view === "about" && (
            <>
              <section className="page-heading">
                <div>
                  <h1>זיהוי צורך. בנייה. הטמעה.</h1>
                  <p>
                    פרויקט שפיתח Guy Hadad Rosenblum עבור רשות האסדרה הישראלית.
                  </p>
                </div>
                <a
                  className="primary"
                  href={repo}
                  target="_blank"
                  rel="noreferrer"
                >
                  <GitBranch size={17} />
                  צפייה בקוד
                </a>
              </section>
              <section className="story">
                <div>
                  <h2>הבעיה התחילה בעבודה עצמה.</h2>
                  <p>
                    ניטור ידני של רגולציות חדשות דרש מעבר חוזר על אתר החקיקה
                    והצלבה עם פניות רשמיות שהגיעו לרשות. העבודה חזרה על עצמה
                    והקשתה על זיהוי פערים בזמן.
                  </p>
                  <p>
                    המערכת נבנתה כדי לאסוף את הפרסומים, להשוות את תוכן המסמכים
                    לפניות ולהכין תוצרים לצוות. היא הוטמעה בתהליך העבודה וחסכה
                    שעות של בדיקה ידנית.
                  </p>
                  <p className="quiet">
                    הגרסה כאן מציגה את התהליך עם נתוני הדגמה. לא מוצג אומדן
                    מספרי לחיסכון ללא מדידה מתועדת.
                  </p>
                </div>
                <aside className="architecture">
                  <h3>מה נמצא מאחורי המסך</h3>
                  <dl>
                    <dt>ממשק</dt>
                    <dd>React · TypeScript</dd>
                    <dt>שכבת שירות</dt>
                    <dd>FastAPI · Python</dd>
                    <dt>איסוף והצלבה</dt>
                    <dd>Selenium · pandas · Jaccard</dd>
                    <dt>סיכום אופציונלי</dt>
                    <dd>Google Vertex AI</dd>
                    <dt>העברה לצוות</dt>
                    <dd>Excel · Monday</dd>
                  </dl>
                </aside>
              </section>
              <section className="matching-lab">
                <div>
                  <h2>איך נמדדת התאמה?</h2>
                  <p>
                    המנוע משווה את קבוצות המילים בשני מסמכים, לאחר סינון לפי
                    משרד וחלון של 120 יום. אפשר לשנות את הטקסט ולראות את המדד
                    מחושב מיד.
                  </p>
                </div>
                <div className="lab-inputs">
                  <label>
                    טקסט הפרסום
                    <textarea
                      value={a}
                      onChange={(e) => setA(e.target.value)}
                    />
                  </label>
                  <label>
                    טקסט הפנייה
                    <textarea
                      value={b}
                      onChange={(e) => setB(e.target.value)}
                    />
                  </label>
                  <div className="similarity-result">
                    <strong>
                      {similarity(a, b).toFixed(1)}
                      <small>%</small>
                    </strong>
                    <span>דמיון מילולי</span>
                    <p>
                      סף ההצלבה במנוע: 55%. זהו מדד דמיון, לא הסתברות לנכונות
                      ההתאמה.
                    </p>
                  </div>
                </div>
              </section>
            </>
          )}
          <footer className="footer">
            <span>נבנה מתוך צורך אמיתי בעבודה.</span>
            <a href={repo} target="_blank" rel="noreferrer">
              Guy Hadad Rosenblum <ArrowUpLeft size={14} />
            </a>
          </footer>
        </main>
      </div>
      <dialog
        ref={dialog}
        onCancel={() => setSelected(null)}
        onClick={(e) => {
          if (e.target === dialog.current) setSelected(null);
        }}
      >
        {selected && (
          <>
            <div className="dialog-header">
              <span className={"status " + selected.status}>
                {labels[selected.status]}
              </span>
              <button
                className="icon-button"
                aria-label="סגירת פרטים"
                onClick={() => setSelected(null)}
              >
                <X />
              </button>
            </div>
            <h2>{selected.title}</h2>
            <p className="quiet">
              {selected.ministry} · {selected.date}
            </p>
            <p>
              {selected.summary ||
                "אין סיכום זמין. אפשר להפעיל סיכום AI בהגדרות המקומיות."}
            </p>
            <dl className="detail-grid">
              <div>
                <dt>דמיון מסמכים</dt>
                <dd>{selected.score}%</dd>
              </div>
              <div>
                <dt>הערכת השפעות</dt>
                <dd>{riaLabels[selected.ria]}</dd>
              </div>
              <div>
                <dt>פנייה רשמית</dt>
                <dd>{selected.submissionDate || "לא נמצאה"}</dd>
              </div>
            </dl>
            <div className="inline-note">
              {mode === "demo"
                ? "רשומת הדגמה סינתטית. הסיכום נכתב לצורך ההדגמה."
                : "ההתאמה והסיווג האוטומטי הם כלי עזר לבדיקה אנושית."}
            </div>
            {/^https?:\/\//.test(selected.url) && (
              <a
                href={selected.url}
                className="secondary"
                target="_blank"
                rel="noreferrer"
              >
                פתיחת המקור <ExternalLink size={15} />
              </a>
            )}
          </>
        )}
      </dialog>
    </div>
  );
}

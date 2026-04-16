// ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────
var FILE_ID = "19Dckip-8PTdH5eMTK2Jx4JFG4gct7IeW";

function doGet() {
  var csvData = "";
  try {
    csvData = DriveApp.getFileById(FILE_ID).getBlob().getDataAsString("UTF-8");
  } catch(e) {
    csvData = "ERROR: " + e.message;
  }
  return HtmlService.createHtmlOutput(buildDashboard(csvData))
    .setTitle("Order Flow Dashboard")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getCsvData() {
  return DriveApp.getFileById(FILE_ID).getBlob().getDataAsString("UTF-8");
}

function buildDashboard(csvData) {
  var escaped = csvData.replace(/\\/g, "\\\\").replace(/`/g, "\\`");

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Order Flow Dashboard</title>
<style>
:root {
  --bg:#0d0d0f; --bg2:#16161a; --bg3:#1e1e24;
  --border:rgba(255,255,255,0.07); --border2:rgba(255,255,255,0.13);
  --text:#e8e8ec; --text2:#9090a0; --text3:#5a5a6a;
  --green:#00c878; --green-bg:rgba(0,200,120,0.08);
  --red:#ff4d4d; --red-bg:rgba(255,77,77,0.08);
  --yellow:#f0a500; --yellow-bg:rgba(240,165,0,0.08);
  --blue:#4d9fff; --radius:8px;
  --font:'SF Mono','Fira Code',monospace;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:var(--font);font-size:12px;min-height:100vh;}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid var(--border);background:var(--bg2);}
.symbol{font-size:15px;font-weight:700;}
.badge{background:var(--bg3);border:1px solid var(--border2);border-radius:4px;padding:2px 7px;font-size:10px;color:var(--text2);margin-left:6px;}
.status{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text2);}
.dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}
.dot.loading{background:var(--yellow);animation:pulse 0.5s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.refresh-bar{padding:6px 16px;border-bottom:1px solid var(--border);background:var(--bg2);display:flex;align-items:center;gap:10px;font-size:11px;color:var(--text2);}
.refresh-bar select{background:var(--bg3);border:1px solid var(--border2);border-radius:4px;color:var(--text);font-family:var(--font);font-size:11px;padding:2px 6px;outline:none;}
.main{padding:12px 16px;display:flex;flex-direction:column;gap:10px;}
.summary-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;}
.metric{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:8px 10px;}
.metric-label{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:3px;}
.metric-value{font-size:16px;font-weight:700;line-height:1;}
.metric-sub{font-size:10px;color:var(--text2);margin-top:2px;}
.up{color:var(--green);} .down{color:var(--red);} .warn{color:var(--yellow);} .neutral{color:var(--text2);}
.signals-row{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;}
.signal-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:8px 10px;display:flex;align-items:center;gap:8px;}
.sig-icon{width:28px;height:28px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;}
.sig-icon.short{background:var(--red-bg);border:1px solid rgba(255,77,77,0.25);}
.sig-icon.long{background:var(--green-bg);border:1px solid rgba(0,200,120,0.25);}
.sig-icon.inactive{background:var(--bg3);border:1px solid var(--border);}
.sig-icon.warn{background:var(--yellow-bg);border:1px solid rgba(240,165,0,0.25);}
.sig-name{font-size:9px;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px;}
.sig-val{font-size:12px;font-weight:600;margin-top:1px;}
.sig-val.short{color:var(--red);} .sig-val.long{color:var(--green);} .sig-val.warn{color:var(--yellow);} .sig-val.neutral{color:var(--text2);}
.checklists{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;}
.checklist{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;}
.checklist.active-short{border-color:rgba(255,77,77,0.4);}
.checklist.active-long{border-color:rgba(0,200,120,0.4);}
.checklist.active-warn{border-color:rgba(240,165,0,0.4);}
.cl-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;}
.cl-title{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.7px;}
.cl-title.short{color:var(--red);} .cl-title.long{color:var(--green);} .cl-title.warn{color:var(--yellow);}
.cl-score{font-size:12px;font-weight:700;}
.cl-subtitle{font-size:9px;color:var(--text3);margin-bottom:7px;padding-bottom:5px;border-bottom:1px solid var(--border);line-height:1.4;}
.cl-items{display:flex;flex-direction:column;gap:3px;}
.ci{display:flex;align-items:flex-start;gap:6px;padding:3px 6px;border-radius:3px;}
.ci.ok{background:var(--green-bg);}
.ci.fail{background:rgba(255,255,255,0.02);}
.ci.partial{background:var(--yellow-bg);}
.ci-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;margin-top:4px;}
.ci-dot.ok{background:var(--green);} .ci-dot.fail{background:var(--text3);} .ci-dot.partial{background:var(--yellow);}
.ci-label{flex:1;color:var(--text2);font-size:10px;line-height:1.4;}
.ci.ok .ci-label{color:var(--text);} .ci.partial .ci-label{color:var(--yellow);}
.ci-val{font-size:9px;color:var(--text3);min-width:48px;text-align:right;margin-top:2px;flex-shrink:0;}
.ci.ok .ci-val{color:var(--green);opacity:0.75;}
.verdict{margin-top:7px;padding:5px 8px;border-radius:4px;font-size:10px;font-weight:600;text-align:center;}
.verdict.short{background:rgba(255,77,77,0.12);border:1px solid rgba(255,77,77,0.3);color:var(--red);}
.verdict.long{background:rgba(0,200,120,0.12);border:1px solid rgba(0,200,120,0.3);color:var(--green);}
.verdict.watch{background:var(--yellow-bg);border:1px solid rgba(240,165,0,0.3);color:var(--yellow);}
.verdict.neutral{background:var(--bg3);border:1px solid var(--border);color:var(--text3);}
.analysis-section{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;}
.analysis-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--border);}
.analysis-title{font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:var(--text2);}
.analysis-bias{font-size:12px;font-weight:700;padding:3px 10px;border-radius:4px;}
.analysis-bias.bull{background:var(--green-bg);color:var(--green);border:1px solid rgba(0,200,120,0.3);}
.analysis-bias.bear{background:var(--red-bg);color:var(--red);border:1px solid rgba(255,77,77,0.3);}
.analysis-bias.neutral{background:var(--bg3);color:var(--text2);border:1px solid var(--border);}
.finding{display:flex;align-items:flex-start;gap:8px;padding:5px 8px;border-radius:4px;margin-bottom:3px;}
.finding.high{background:rgba(255,255,255,0.03);border-left:2px solid var(--yellow);}
.finding.medium{background:rgba(255,255,255,0.015);border-left:2px solid var(--border2);}
.finding-icon{font-size:12px;flex-shrink:0;margin-top:1px;}
.finding-type{font-size:8px;text-transform:uppercase;letter-spacing:0.6px;color:var(--text3);font-weight:600;}
.finding-msg{font-size:11px;color:var(--text2);margin-top:1px;line-height:1.4;}
.finding.high .finding-msg{color:var(--text);}
.action-panel{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;}
.action-panel.dir-short{border-color:rgba(255,77,77,0.35);}
.action-panel.dir-long{border-color:rgba(0,200,120,0.35);}
.action-main{display:flex;align-items:flex-start;gap:12px;padding:12px 16px;}
.action-arrow{font-size:22px;flex-shrink:0;line-height:1;margin-top:2px;}
.action-body{flex:1;min-width:0;}
.action-narrative{font-size:13px;font-weight:600;color:var(--text);line-height:1.5;}
.action-winner{font-size:10px;color:var(--text2);margin-top:4px;}
.action-conf{display:flex;align-items:center;gap:6px;flex-shrink:0;margin-top:4px;}
.conf-track{width:50px;height:4px;background:var(--bg3);border-radius:2px;overflow:hidden;}
.conf-fill{height:100%;border-radius:2px;}
.conf-label{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:0.5px;}
.setup-pills{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:8px 16px;border-top:1px solid var(--border);}
.pill{display:flex;align-items:center;gap:6px;opacity:0.4;transition:opacity 0.2s;}
.pill.active{opacity:1;}
.pill-label{font-size:9px;color:var(--text2);text-transform:uppercase;letter-spacing:0.3px;min-width:70px;white-space:nowrap;}
.pill.active .pill-label{color:var(--text);font-weight:600;}
.pill-bar{flex:1;height:4px;background:var(--bg3);border-radius:2px;overflow:hidden;min-width:30px;}
.pill-fill{height:100%;border-radius:2px;transition:width 0.3s;}
.pill-fill.short{background:var(--red);} .pill-fill.long{background:var(--green);} .pill-fill.neutral{background:var(--text3);}
.pill-score{font-size:10px;color:var(--text3);font-weight:600;min-width:24px;text-align:right;}
.pill.active .pill-score{color:var(--text);}
.action-toggle{padding:6px 16px;border-top:1px solid var(--border);font-size:10px;color:var(--text2);cursor:pointer;user-select:none;}
.action-toggle:hover{background:rgba(255,255,255,0.02);color:var(--text);}
.action-details{padding:12px 16px;border-top:1px solid var(--border);display:none;}
.action-details.open{display:block;}
.details-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;}
.all-setups-toggle{font-size:10px;color:var(--text2);cursor:pointer;user-select:none;padding:6px 0;margin-top:8px;}
.all-setups-toggle:hover{color:var(--text);}
.all-setups{display:none;margin-top:8px;}
.all-setups.open{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;}
.table-section{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;}
.table-header{padding:7px 12px;border-bottom:1px solid var(--border);font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:var(--text2);}
.table-scroll{overflow-x:auto;}
table{width:100%;border-collapse:collapse;table-layout:fixed;}
col.c-time{width:50px;} col.c-close{width:74px;} col.c-hl{width:90px;}
col.c-vol{width:58px;} col.c-vrel{width:40px;}
col.c-delta{width:66px;} col.c-bs{width:50px;} col.c-cvd{width:58px;}
col.c-oipct{width:110px;} col.c-dpct{width:48px;} col.c-flag{width:76px;}
th{font-size:9px;text-transform:uppercase;letter-spacing:0.6px;color:var(--text3);padding:5px 8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap;}
th:first-child{text-align:left;}
td{padding:4px 8px;text-align:right;border-bottom:1px solid rgba(255,255,255,0.04);font-size:11px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
td:first-child{text-align:left;color:var(--text);font-weight:500;}
tr:last-child td{border-bottom:none;}
tr.hl td{background:rgba(255,255,255,0.025);}
tr.ar td{background:rgba(255,77,77,0.05);}
tr.ag td{background:rgba(0,200,120,0.05);}
tr.abs-bear td{background:rgba(255,140,0,0.08);}
tr.abs-bull td{background:rgba(138,43,226,0.08);}
.tp{color:var(--green);font-weight:500;} .tn{color:var(--red);font-weight:500;} .tw{color:var(--yellow);} .tb{color:var(--blue);}
.dv-l2{color:var(--green);font-weight:700;} .dv-l1{color:rgba(0,200,120,0.6);} .dv-s1{color:rgba(255,77,77,0.6);} .dv-s2{color:var(--red);font-weight:700;}
.tag{display:inline-block;font-size:8px;padding:1px 4px;border-radius:2px;margin-left:2px;font-weight:600;}
.tag.s{background:var(--red-bg);color:var(--red);border:1px solid rgba(255,77,77,0.2);}
.tag.l{background:var(--green-bg);color:var(--green);border:1px solid rgba(0,200,120,0.2);}
.tag.v{background:var(--yellow-bg);color:var(--yellow);border:1px solid rgba(240,165,0,0.2);}
.tbl-legend{padding:5px 12px;border-top:1px solid var(--border);font-size:9px;color:var(--text3);display:flex;gap:14px;flex-wrap:wrap;}
.footer{padding:7px 16px;border-top:1px solid var(--border);font-size:10px;color:var(--text3);display:flex;justify-content:space-between;}
@media(max-width:900px){.checklists,.all-setups.open{grid-template-columns:1fr 1fr;}.setup-pills{grid-template-columns:1fr 1fr;}}
@media(max-width:600px){.summary-grid,.signals-row,.checklists,.all-setups.open{grid-template-columns:1fr 1fr;}.setup-pills{grid-template-columns:1fr 1fr;}.details-grid{grid-template-columns:1fr;}}
</style>
</head>
<body>

<div class="topbar">
  <div style="display:flex;align-items:center;">
    <span class="symbol" id="sym">BTCUSDT</span>
    <span class="badge" id="tf">5M</span>
    <span class="badge" id="gen-time">--:--</span>
  </div>
  <div class="status"><div class="dot" id="dot"></div><span id="status-txt">Cargando...</span></div>
</div>

<div class="refresh-bar">
  <span>Refresh:</span>
  <select id="ri" onchange="scheduleRefresh()">
    <option value="0">Off</option>
    <option value="30">30s</option>
    <option value="60" selected>1min</option>
    <option value="120">2min</option>
    <option value="300">5min</option>
  </select>
  <span id="next-r" style="color:var(--text3);">—</span>
  <button onclick="fetchAndRender()" style="background:var(--bg3);border:1px solid var(--border2);border-radius:4px;color:var(--text);font-family:var(--font);font-size:10px;padding:2px 8px;cursor:pointer;">Actualizar</button>
  <span style="margin-left:auto;color:var(--text3);font-size:10px;" id="ft">—</span>
</div>

<div class="main" id="main"></div>
<div class="footer"><span>Order Flow · Playbook Lucas</span><span>Actualiza con cada .bat</span></div>

<script>
var INITIAL_CSV = \`${escaped}\`;
var refreshTimer = null;
var secsLeft = 0;

function scheduleRefresh() {
  clearInterval(refreshTimer);
  var s = parseInt(document.getElementById('ri').value);
  document.getElementById('next-r').textContent = s ? 'próximo: '+s+'s' : '—';
  if (!s) return;
  secsLeft = s;
  refreshTimer = setInterval(function() {
    secsLeft--;
    document.getElementById('next-r').textContent = 'próximo: '+secsLeft+'s';
    if (secsLeft <= 0) { secsLeft = parseInt(document.getElementById('ri').value); fetchAndRender(); }
  }, 1000);
}

function fetchAndRender() {
  var dot = document.getElementById('dot');
  dot.className = 'dot loading';
  google.script.run
    .withSuccessHandler(function(csv) {
      try { render(parseCSV(csv)); dot.className='dot'; setUpdated(); } catch(e) { dot.className='dot'; }
    })
    .withFailureHandler(function() { dot.className='dot'; })
    .getCsvData();
}

function setUpdated() {
  document.getElementById('status-txt').textContent = 'Actualizado '+new Date().toLocaleTimeString('es-AR');
  document.getElementById('ft').textContent = new Date().toLocaleString('es-AR');
}

function parseCSV(text) {
  var lines = text.split('\\n').map(function(l){return l.trim();}).filter(Boolean);
  var summary={}, rows=[], findings=[], overall={bias:'NEUTRAL',bull:0,bear:0}, action=null, section='header';
  for (var i=0;i<lines.length;i++) {
    var line=lines[i], cols=line.split(',');
    if (line==='analysis'){section='analysis';i++;continue;}
    if (line.indexOf('overall,')===0){var oc=line.split(',');overall={bias:oc[1],bull:parseInt(oc[2])||0,bear:parseInt(oc[3])||0};continue;}
    if (line.indexOf('action,')===0){var ac=line.match(/^action,([^,]*),([^,]*),(.*)$/);if(ac)action={direction:ac[1],confidence:ac[2],narrative:ac[3].replace(/^"|"$/g,'')};continue;}
    if (section==='header'){
      if (cols[0]==='generated'){i++;var v=lines[i].split(',');
        summary={generated:v[0],symbol:v[1],tf:v[2],daily_low:parseFloat(v[3]),daily_high:parseFloat(v[4]),
          pct_range:parseFloat(v[5]),vwap:parseFloat(v[6]),vwap_bias:v[7],vwap_dev:parseFloat(v[8]),
          session_cvd:parseFloat(v[9]),current_oi:parseFloat(v[10])};}
      if (cols[0]==='time'){section='candles';}
    } else if (section==='candles'){
      if (cols.length<5) continue;
      // cols: time,close,high,low,volume,delta,delta_pct,buy_pct,sell_pct,cvd,vwap,oi,oi_delta,vol_rel
      rows.push({time:cols[0],close:parseFloat(cols[1]),high:parseFloat(cols[2]),low:parseFloat(cols[3]),
        vol:parseFloat(cols[4]),delta:parseFloat(cols[5]),delta_pct:parseFloat(cols[6]),
        buy_pct:parseFloat(cols[7]),sell_pct:parseFloat(cols[8]),cvd:parseFloat(cols[9]),
        vwap:parseFloat(cols[10]),oi:cols[11]?parseFloat(cols[11]):null,
        oi_delta:cols[12]!==undefined&&cols[12]!==''?parseFloat(cols[12]):null,
        vol_rel:cols[13]?parseFloat(cols[13]):null});
    } else if (section==='analysis'){
      var m=line.match(/^([^,]*),([^,]*),([^,]*),(.*)$/);
      if (m) findings.push({type:m[1],severity:m[2],bias:m[3],msg:m[4].replace(/^"|"$/g,'')});
    }
  }
  return {summary:summary,rows:rows,findings:findings,overall:overall,action:action};
}

function fmtN(n,d){
  d=d===undefined?1:d;
  if(n===null||isNaN(n))return'—';
  var abs=Math.abs(n),sign=n>=0?'+':'-';
  if(abs>=1e6)return sign+(abs/1e6).toFixed(d)+'M';
  if(abs>=1e3)return sign+(abs/1e3).toFixed(d)+'K';
  return(n>=0?'+':'')+n.toFixed(d);
}
function fmtV(n,d){
  d=d===undefined?1:d;
  if(n===null||isNaN(n))return'—';
  if(n>=1e6)return(n/1e6).toFixed(d)+'M';
  if(n>=1e3)return(n/1e3).toFixed(d)+'K';
  return n.toFixed(d);
}
function fmtP(n){
  if(!n&&n!==0)return'—';
  return n.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1});
}

function analyzePlaybook(data) {
  var rows=data.rows, s=data.summary;
  if(!rows.length) return {};
  var last=rows[rows.length-1];
  var r5=rows.slice(-5);
  var negC=r5.filter(function(r){return r.delta<0;}).length;
  var posC=r5.filter(function(r){return r.delta>0;}).length;
  var deltaBear=negC>=3, deltaBull=posC>=3;
  var oiV=r5.filter(function(r){return r.oi!==null;}).map(function(r){return r.oi;});
  var oiT=null;
  if(oiV.length>=2){var dd=oiV[oiV.length-1]-oiV[0];oiT=dd>50?'rising':dd<-50?'falling':'flat';}
  var cvds=r5.map(function(r){return r.cvd;}).filter(function(v){return v!==null;});
  var cvdFalling=cvds.length>=2&&cvds[cvds.length-1]<cvds[0];
  var cvdRising=cvds.length>=2&&cvds[cvds.length-1]>cvds[0];
  var aboveVwap=s.vwap_bias==='bull', belowVwap=s.vwap_bias==='bear';
  var vwapExt=Math.abs(s.vwap_dev)>0.8;
  var zonaAlta=s.pct_range>70, zonaBaja=s.pct_range<30;
  var avgVol=rows.reduce(function(a,r){return a+r.vol;},0)/rows.length;
  var lowVol=r5.every(function(r){return r.vol<avgVol*1.3;});
  var sinBearish=last.delta>-150&&last.buy_pct>=43;
  var squeezeRisk=last.vol>avgVol*2&&Math.abs(last.delta)>300&&oiT==='rising';
  var netDelta5=r5.reduce(function(a,r){return a+r.delta;},0);
  var cvdDropFast=cvds.length>=2&&(cvds[0]-cvds[cvds.length-1]>500);

  var shortDistChecks=[
    {label:'Zona alta del rango (>70%) — confirmá nivel HTF',ok:zonaAlta,partial:s.pct_range>60&&!zonaAlta,val:s.pct_range.toFixed(0)+'%'},
    {label:'Delta negativo persistente (3+ de 5)',ok:deltaBear,val:negC+'/5 neg'},
    {label:'OI subiendo — shorts institucionales entrando',ok:oiT==='rising',val:oiT||'—'},
    {label:'CVD cayendo — compradores cediendo',ok:cvdFalling,val:fmtN(s.session_cvd)},
    {label:'Precio sobre VWAP o extensión (>0.8%)',ok:aboveVwap||vwapExt,val:(s.vwap_dev>=0?'+':'')+s.vwap_dev.toFixed(2)+'%'},
  ];
  var shortAgroChecks=[
    {label:'Delta muy negativo neto (impulso bajista)',ok:deltaBear&&netDelta5<-200,val:fmtN(netDelta5)},
    {label:'CVD cayendo rápido (aceleración vendedora)',ok:cvdFalling&&cvdDropFast,val:fmtN(s.session_cvd)},
    {label:'OI subiendo — nuevos shorts abriendo',ok:oiT==='rising',val:oiT||'—'},
    {label:'Precio bajo VWAP o perdiéndolo',ok:belowVwap||s.vwap_dev<-0.3,val:(s.vwap_dev>=0?'+':'')+s.vwap_dev.toFixed(2)+'%'},
    {label:'⚠ Confirmá: Gold Sell Drugas 15M + LHs',ok:false,partial:true,val:'chart req.'},
  ];
  var longFavorChecks=[
    {label:'OI bajando/plano — sesgo HTF alcista',ok:oiT==='falling'||oiT==='flat',val:oiT||'—'},
    {label:'CVD positivo y subiendo',ok:cvdRising&&s.session_cvd>0,val:fmtN(s.session_cvd)},
    {label:'Vol bajo en pullback (sin presión vendedora)',ok:lowVol,val:lowVol?'bajo':'alto'},
    {label:'Sin señal bajista fresca en delta',ok:sinBearish,val:sinBearish?'limpio':'bear'},
    {label:'⚠ Confirmá: nivel lógico en chart (D PP/VWAP)',ok:false,partial:true,val:'chart req.'},
  ];
  var longReboteChecks=[
    {label:'Zona baja del rango (<30%) — confirmá nivel HTF',ok:zonaBaja,partial:s.pct_range<40&&!zonaBaja,val:s.pct_range.toFixed(0)+'%'},
    {label:'OI bajando — shorts cerrando (squeeze posible)',ok:oiT==='falling',val:oiT||'—'},
    {label:'Delta positivo — compradores entrando',ok:deltaBull,val:posC+'/5 pos'},
    {label:'CVD girando positivo',ok:cvdRising,val:fmtN(s.session_cvd)},
    {label:'Precio bajo VWAP (zona de rebote natural)',ok:belowVwap,val:belowVwap?'bajo VWAP':'sobre VWAP'},
  ];

  function score(c){return c.filter(function(x){return x.ok&&!x.partial;}).length;}
  function maxScore(c){return c.filter(function(x){return !x.partial;}).length;}

  var setups=[
    {id:'short-dist',label:'SHORT DIST.',checks:shortDistChecks,score:score(shortDistChecks),max:maxScore(shortDistChecks),dir:'short'},
    {id:'short-agro',label:'SHORT AGRO.',checks:shortAgroChecks,score:score(shortAgroChecks),max:maxScore(shortAgroChecks),dir:'short'},
    {id:'long-htf',label:'LONG HTF',checks:longFavorChecks,score:score(longFavorChecks),max:maxScore(longFavorChecks),dir:'long'},
    {id:'rebote',label:'REBOTE',checks:longReboteChecks,score:score(longReboteChecks),max:maxScore(longReboteChecks),dir:'long'}
  ];
  setups.sort(function(a,b){return (b.score/b.max)-(a.score/a.max);});
  var winner=setups[0];

  return {s:s,rows:rows,last:last,avgVol:avgVol,deltaBear:deltaBear,deltaBull:deltaBull,
    oiT:oiT,zonaAlta:zonaAlta,zonaBaja:zonaBaja,squeezeRisk:squeezeRisk,aboveVwap:aboveVwap,
    shortDistChecks:shortDistChecks,shortAgroChecks:shortAgroChecks,
    longFavorChecks:longFavorChecks,longReboteChecks:longReboteChecks,
    shortDistScore:score(shortDistChecks),shortAgroScore:score(shortAgroChecks),
    longFavorScore:score(longFavorChecks),longReboteScore:score(longReboteChecks),
    setups:setups,winner:winner};
}

function metric(l,v,s,c,tt){return '<div class="metric"'+(tt?' title="'+tt+'"':'')+'>'+
  '<div class="metric-label">'+l+'</div><div class="metric-value '+c+'">'+v+'</div><div class="metric-sub">'+s+'</div></div>';}
function signal(n,v,t,i,tt){return '<div class="signal-card"'+(tt?' title="'+tt+'"':'')+'>'+
  '<div class="sig-icon '+t+'">'+i+'</div><div><div class="sig-name">'+n+'</div><div class="sig-val '+t+'">'+v+'</div></div></div>';}

function checklist(title,subtitle,checks,score,dir){
  var maxR=checks.filter(function(c){return !c.partial;}).length;
  var isShort=dir==='short'||dir==='short-agro';
  var col=score>=maxR-1?(isShort?'var(--red)':'var(--green)'):score>=maxR-2?'var(--yellow)':'var(--text3)';
  var tcls=dir==='short'?'short':dir==='short-agro'?'warn':'long';
  var bcls=score>=maxR-1?(isShort?'active-short':'active-long'):score>=maxR-2?'active-warn':'';
  var h='<div class="checklist '+bcls+'">';
  h+='<div class="cl-header"><span class="cl-title '+tcls+'">'+title+'</span><span class="cl-score" style="color:'+col+'">'+score+'/'+maxR+'</span></div>';
  h+='<div class="cl-subtitle">'+subtitle+'</div><div class="cl-items">';
  checks.forEach(function(c){
    var st=c.partial?'partial':c.ok?'ok':'fail';
    h+='<div class="ci '+st+'"><div class="ci-dot '+st+'"></div><span class="ci-label">'+c.label+'</span><span class="ci-val">'+c.val+'</span></div>';
  });
  h+='</div>';
  var vt,vx;
  if(score>=maxR-1){vt=isShort?'short':'long';vx=dir==='short'?'FLUJO SHORT — buscá entrada':dir==='short-agro'?'FLUJO BAJISTA FUERTE':dir==='long-favor'?'FLUJO LONG — pullback al nivel':'FLUJO REBOTE — buscá absorción';}
  else if(score>=maxR-2){vt='watch';vx='Flujo parcial — '+score+'/'+maxR;}
  else{vt='neutral';vx='Sin flujo';}
  return h+'<div class="verdict '+vt+'">'+vx+'</div></div>';
}

function renderAnalysis(findings,overall){
  if(!findings||!findings.length) return '';
  var bc=overall.bias.indexOf('ALCISTA')>=0||overall.bias.indexOf('↑')>=0?'bull':overall.bias.indexOf('BAJISTA')>=0||overall.bias.indexOf('↓')>=0?'bear':'neutral';
  var h='<div class="analysis-section"><div class="analysis-header"><span class="analysis-title">Auto-Análisis Python</span><span class="analysis-bias '+bc+'">'+overall.bias+' ('+overall.bull+'↑ / '+overall.bear+'↓)</span></div>';
  var hi=findings.filter(function(f){return f.severity==='high';});
  var me=findings.filter(function(f){return f.severity==='medium';});
  if(hi.length){h+='<div style="font-size:9px;color:var(--yellow);text-transform:uppercase;letter-spacing:0.6px;margin:4px 0;font-weight:600;">⚠ Señales fuertes</div>';
    hi.forEach(function(f){var i=f.bias==='bear'?'🔴':f.bias==='bull'?'🟢':'🟡';h+='<div class="finding high"><span class="finding-icon">'+i+'</span><div><div class="finding-type">'+f.type+'</div><div class="finding-msg">'+f.msg+'</div></div></div>';});}
  if(me.length){h+='<div style="font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:0.6px;margin:6px 0 3px;font-weight:600;">📊 Contexto</div>';
    me.forEach(function(f){var i=f.bias==='bear'?'🔻':f.bias==='bull'?'🔹':'◽';h+='<div class="finding medium"><span class="finding-icon">'+i+'</span><div><div class="finding-type">'+f.type+'</div><div class="finding-msg">'+f.msg+'</div></div></div>';});}
  return h+'</div>';
}

function buildNarrative(winner,findings,overall){
  var isShort=winner.dir==='short';
  var dir=isShort?'BAJISTA':'ALCISTA';
  var targetBias=isShort?'bear':'bull';
  var matching=findings.filter(function(f){return f.bias===targetBias;});
  if(!matching.length) matching=findings.filter(function(f){return f.severity==='high';});
  var reasons=[];
  matching.slice(0,3).forEach(function(f){
    var parts=f.msg.split('→');
    if(parts.length>1) reasons.push(parts[parts.length-1].trim());
    else reasons.push(f.msg);
  });
  if(!reasons.length) return 'Sin senal dominante — esperar confluencia';
  return 'Flujo '+dir+' — '+reasons.join(', ');
}

function renderActionPanel(data,a){
  var w=a.winner;
  var isShort=w.dir==='short';
  var dirCls=w.score>=w.max-1?(isShort?'dir-short':'dir-long'):'';
  var action=data.action;
  var narrative=action?action.narrative:buildNarrative(w,data.findings,data.overall);
  var confidence=action?action.confidence:(w.score>=w.max-1?'high':w.score>=w.max-2?'medium':'low');
  var confPct=confidence==='high'?100:confidence==='medium'?60:30;
  var confColor=isShort?'var(--red)':'var(--green)';
  if(confidence==='low') confColor='var(--text3)';
  var arrow=isShort?'▼':'▲';
  var arrowColor=isShort?'var(--red)':'var(--green)';
  if(w.score<w.max-2){arrow='─';arrowColor='var(--text3)';}

  var h='<div class="action-panel '+dirCls+'">';

  // Layer 1: Main action
  h+='<div class="action-main">';
  h+='<div class="action-arrow" style="color:'+arrowColor+'">'+arrow+'</div>';
  h+='<div class="action-body">';
  h+='<div class="action-narrative">'+narrative+'</div>';
  h+='<div class="action-winner">'+w.label+' '+w.score+'/'+w.max+'</div>';
  h+='</div>';
  h+='<div class="action-conf">';
  h+='<div class="conf-track"><div class="conf-fill" style="width:'+confPct+'%;background:'+confColor+';"></div></div>';
  h+='<span class="conf-label">'+confidence+'</span>';
  h+='</div>';
  h+='</div>';

  // Layer 2: Setup pills
  h+='<div class="setup-pills">';
  a.setups.forEach(function(su){
    var isActive=su.id===w.id;
    var pct=su.max>0?Math.round((su.score/su.max)*100):0;
    var fillCls=su.dir==='short'?'short':'long';
    if(su.score<su.max-2) fillCls='neutral';
    h+='<div class="pill'+(isActive?' active':'')+'">';
    h+='<span class="pill-label">'+su.label+'</span>';
    h+='<div class="pill-bar"><div class="pill-fill '+fillCls+'" style="width:'+pct+'%"></div></div>';
    h+='<span class="pill-score">'+su.score+'/'+su.max+'</span>';
    h+='</div>';
  });
  h+='</div>';

  // Layer 3: Toggle + details
  h+='<div class="action-toggle" onclick="toggleDetails()">▸ Ver detalles</div>';
  h+='<div class="action-details" id="action-details">';

  // Winner checklist + findings side by side
  h+='<div class="details-grid">';
  var wDir=w.id==='short-dist'?'short':w.id==='short-agro'?'short-agro':w.id==='long-htf'?'long-favor':'long';
  var wTitle=isShort?'🔴 '+w.label:'🟢 '+w.label;
  var wSub=w.id==='short-dist'?'Impulso alcista + nivel HTF + flujo bajista acumulando':w.id==='short-agro'?'Sin retesteo. Triple confluencia + Gold Sell Drugas 15M':w.id==='long-htf'?'Pullback a nivel lógico. Sin absorción masiva requerida.':'Contra HTF. Espejo del Short Dist. OI bajando = squeeze';
  h+=checklist(wTitle,wSub,w.checks,w.score,wDir);
  h+=renderAnalysis(data.findings,data.overall);
  h+='</div>';

  // All setups toggle
  h+='<div class="all-setups-toggle" onclick="toggleAllSetups()">▸ Comparar todos los setups</div>';
  h+='<div class="all-setups" id="all-setups">';
  h+=checklist('🔴 Short Dist.','Impulso alcista + nivel HTF + flujo bajista acumulando',a.shortDistChecks,a.shortDistScore,'short');
  h+=checklist('🔴 Short Agro.','Sin retesteo. Triple confluencia + Gold Sell Drugas 15M',a.shortAgroChecks,a.shortAgroScore,'short-agro');
  h+=checklist('🟢 Long HTF','Pullback a nivel lógico. Sin absorción masiva requerida.',a.longFavorChecks,a.longFavorScore,'long-favor');
  h+=checklist('🟢 Rebote/Spring','Contra HTF. Espejo del Short Dist. OI bajando = squeeze',a.longReboteChecks,a.longReboteScore,'long');
  h+='</div>';

  h+='</div></div>';
  return h;
}

function toggleDetails(){
  var el=document.getElementById('action-details');
  var isOpen=el.classList.contains('open');
  if(isOpen){el.classList.remove('open');el.previousElementSibling.innerHTML='▸ Ver detalles';}
  else{el.classList.add('open');el.previousElementSibling.innerHTML='▾ Ocultar detalles';}
}
function toggleAllSetups(){
  var el=document.getElementById('all-setups');
  var isOpen=el.classList.contains('open');
  if(isOpen){el.classList.remove('open');el.previousElementSibling.innerHTML='▸ Comparar todos los setups';}
  else{el.classList.add('open');el.previousElementSibling.innerHTML='▾ Ocultar setups';}
}

function render(data){
  var a=analyzePlaybook(data);
  if(!a.s){document.getElementById('main').innerHTML='<p style="color:var(--red);padding:20px;">Error</p>';return;}
  var s=a.s,rows=a.rows;
  document.getElementById('sym').textContent=s.symbol||'BTCUSDT';
  document.getElementById('tf').textContent=s.tf||'5M';
  document.getElementById('gen-time').textContent=s.generated||'';

  var h='';
  h+='<div class="summary-grid">';
  h+=metric('Precio',fmtP(a.last.close),s.pct_range.toFixed(1)+'% rango',s.pct_range>70?'warn':s.pct_range<30?'up':'neutral','Dónde está el precio dentro del rango del día. >70% = zona cara para comprar. <30% = zona cara para vender.');
  h+=metric('CVD Sesión',fmtN(s.session_cvd),s.session_cvd>0?'Net Buyer':'Net Seller',s.session_cvd>0?'up':'down','El flujo real de toda la sesión. Si sube mientras el precio baja, hay compradores absorbiendo. Si cae con precio subiendo, la suba es débil.');
  h+=metric('OI',fmtN(s.current_oi),'Tend: '+(a.oiT||'—'),a.oiT==='rising'?'warn':a.oiT==='falling'?'up':'neutral','Cuántas posiciones abiertas hay. Sube = nuevos jugadores entrando. Baja = posiciones cerrándose. Junto al delta dice quién está apostando.');
  h+=metric('VWAP',fmtP(s.vwap),(s.vwap_dev>=0?'+':'')+s.vwap_dev.toFixed(2)+'%',s.vwap_bias==='bull'?'up':'down','Precio justo de la sesión según el volumen. Alejarse mucho del VWAP suele resolverse volviendo. Es el imán de precio del día.');
  h+=metric('Rango',fmtP(s.daily_low)+'–'+fmtP(s.daily_high),'Amp: '+fmtP(s.daily_high-s.daily_low),'neutral','Extremos del día. La amplitud dice cuánto movimiento hubo. Precio cerca de los extremos = riesgo mayor si operás a favor de ese extremo.');
  h+='</div>';

  h+='<div class="signals-row">';
  h+=signal('Delta',a.deltaBear?'BAJISTA ↓':a.deltaBull?'ALCISTA ↑':'Neutral',a.deltaBear?'short':a.deltaBull?'long':'inactive',a.deltaBear?'🔴':a.deltaBull?'🟢':'⚪','Momentum del flujo en las últimas 5 velas. No es el precio, es quién está empujando más.');
  h+=signal('OI Tend.',a.oiT==='rising'?'SUBIENDO ↑':a.oiT==='falling'?'BAJANDO ↓':'PLANO',a.oiT==='rising'?'warn':a.oiT==='falling'?'long':'inactive',a.oiT==='rising'?'⚠':a.oiT==='falling'?'🟢':'⚪','Sube = nuevas apuestas entrando al mercado. Baja = posiciones cerrándose. Si baja rápido puede desencadenar un squeeze.');
  h+=signal('OI+Delta',a.deltaBear&&a.oiT==='rising'?'SHORTS INST.':a.deltaBull&&a.oiT==='falling'?'CUBRIENDO':'Sin señal',a.deltaBear&&a.oiT==='rising'?'short':a.deltaBull&&a.oiT==='falling'?'long':'inactive',a.deltaBear&&a.oiT==='rising'?'🔴':'⚪','Lo más importante: dice quién está abriendo posiciones. SHORTS INST. = dinero grande apostando a la baja. CUBRIENDO = shorts cerrando a la fuerza.');
  h+=signal('Squeeze',a.squeezeRisk?'POSIBLE':'Ninguno',a.squeezeRisk?'warn':'inactive',a.squeezeRisk?'⚠':'⚪','Presión acumulada lista para explotar. Rango comprimido + OI creciendo + volumen alto = movimiento brusco inminente en cualquier dirección.');
  h+='</div>';

  h+=renderActionPanel(data,a);

  var cvdVals=rows.map(function(r){return r.cvd;});
  var cvdMin=Math.min.apply(null,cvdVals),cvdMax=Math.max.apply(null,cvdVals),cvdRange=cvdMax-cvdMin||1;
  var avgDelta=rows.reduce(function(s,r){return s+Math.abs(r.delta);},0)/rows.length;

  var enriched=rows.map(function(r,i){
    var prevOI=i>0?rows[i-1].oi:null;
    var oiDeltaPct=null;
    if(r.oi_delta!==null&&prevOI!==null&&prevOI!==0){
      oiDeltaPct=(r.oi_delta/prevOI)*100;
    }
    var prevClose=i>0?rows[i-1].close:r.close;
    return Object.assign({},r,{oiDeltaPct:oiDeltaPct,
      absBear:r.buy_pct>60&&r.close<prevClose,absBull:r.sell_pct>60&&r.close>prevClose});
  });

  h+='<div class="table-section">';
  h+='<div class="table-header">Flujo por vela — últimas '+rows.length+' · vol prom: '+fmtN(a.avgVol)+' · Δ prom: '+fmtN(avgDelta)+'</div>';
  h+='<div style="padding:4px 12px;border-bottom:1px solid var(--border);">';
  h+='<div style="font-size:8px;color:var(--text3);margin-bottom:2px;">CVD TREND</div>';
  h+='<div style="display:flex;height:20px;gap:1px;align-items:flex-end;">';
  rows.forEach(function(r){
    var norm=Math.max(((r.cvd-cvdMin)/cvdRange)*100,3);
    var col=r.cvd>=0?'rgba(0,200,120,0.5)':'rgba(255,77,77,0.5)';
    h+='<div style="flex:1;height:'+norm.toFixed(0)+'%;background:'+col+';border-radius:1px;min-width:2px;"></div>';
  });
  h+='</div></div>';

  h+='<div class="table-scroll"><table>';
  h+='<colgroup><col class="c-time"><col class="c-close"><col class="c-hl"><col class="c-vol"><col class="c-vrel"><col class="c-delta"><col class="c-bs"><col class="c-cvd"><col class="c-oipct"><col class="c-dpct"><col class="c-flag"></colgroup>';
  h+='<tr>';
  h+='<th title="Hora UTC-3">Hora</th>';
  h+='<th title="Precio de cierre">Close</th>';
  h+='<th title="High y Low de la vela. El rango te dice si fue una vela de cuerpo o de mechas.">H/L</th>';
  h+='<th title="Participación de la vela. Alto = movimiento con respaldo. Bajo = puede ser ruido o trampa.">Vol</th>';
  h+='<th title="Volumen relativo al promedio de las últimas 20 velas. 1x = normal, 2.5x+ = spike.">VRel</th>';
  h+='<th title="Quién fue más agresivo: compradores o vendedores. No dice quién ganó el precio, sino quién empujó más.">Delta</th>';
  h+='<th title="Balance entre agresores. >60% de un lado = presión unilateral. Cerca de 50/50 = mercado en duda.">B/S</th>';
  h+='<th title="Acumulación neta de la sesión. Sube = el flujo general es comprador aunque el precio baje. Divergencia con precio = señal.">CVD</th>';
  h+='<th title="Cambio de OI en la vela: absoluto y porcentual. Sube = posiciones nuevas entrando. Baja = cierre de posiciones.">OI Δ</th>';
  h+='<th title="Delta como porcentaje del volumen total. +60%: un solo lado dominó la vela. Cerca de 0%: pelea pareja.">Δ%</th>';
  h+='<th title="ABS: vela agresiva absorbida por el lado contrario. ABS*: agresión sin posiciones nuevas. DV: agresión extrema. VOL: vela inusualmente grande.">Flag</th>';
  h+='</tr>';

  enriched.slice().reverse().forEach(function(r,i){
    var flags='';
    var volSpike=r.vol_rel!==null?r.vol_rel>=2.5:r.vol>a.avgVol*2.5;
    if(volSpike) flags+='<span class="tag v">VOL</span>';
    if(Math.abs(r.delta)>avgDelta*2.5) flags+='<span class="tag '+(r.delta>0?'l':'s')+'">Δ'+(r.delta>0?'+':'-')+'</span>';
    if(r.absBear) flags+='<span class="tag s">ABS</span>';
    if(r.absBull) flags+='<span class="tag l">ABS</span>';
    var dpAbs=Math.abs(r.delta_pct);
    if(!isNaN(dpAbs)&&dpAbs>=70) flags+='<span class="tag '+(r.delta_pct>0?'l':'s')+'">DV'+(r.delta_pct>0?'+':'-')+'</span>';
    if(!isNaN(dpAbs)&&dpAbs>=30&&r.oi_delta!==null&&r.vol>0&&Math.abs(r.oi_delta/r.vol)<0.1) flags+='<span class="tag v">ABS*</span>';
    var rc=r.absBear?'abs-bear':r.absBull?'abs-bull':Math.abs(r.delta)>avgDelta*2.5?(r.delta<0?'ar':'ag'):i===0?'hl':'';
    var dc=r.delta>0?'tp':r.delta<0?'tn':'';

    // OI Δ combinado: absoluto / porcentual
    var oiStr='—',oiCls='';
    if(r.oi_delta!==null&&r.oiDeltaPct!==null){
      oiStr=fmtN(r.oi_delta,0)+' / '+(r.oiDeltaPct>=0?'+':'')+r.oiDeltaPct.toFixed(2)+'%';
      oiCls=r.oiDeltaPct>0.15?'tw':r.oiDeltaPct<-0.15?'tn':'';
    } else if(r.oi_delta!==null){
      oiStr=fmtN(r.oi_delta,0);
    }

    // Δ% (reemplaza Δ/V)
    var dpStr='—',dpCls='';
    if(!isNaN(r.delta_pct)){
      dpStr=(r.delta_pct>=0?'+':'')+r.delta_pct.toFixed(0)+'%';
      dpCls=r.delta_pct>=60?'dv-l2':r.delta_pct>=30?'dv-l1':r.delta_pct<=-60?'dv-s2':r.delta_pct<=-30?'dv-s1':'';
    }

    // VRel
    var vrelStr=r.vol_rel!==null?r.vol_rel.toFixed(1)+'x':'—';
    var vrelCls=r.vol_rel>=2.5?'tw':r.vol_rel>=1.5?'tb':'';

    h+='<tr class="'+rc+'">';
    h+='<td>'+(i===0?'▶ ':'')+r.time+'</td>';
    h+='<td>'+fmtP(r.close)+'</td>';
    h+='<td style="font-size:10px;line-height:1.3">'+fmtP(r.high)+'<br><span style="color:var(--text3)">'+fmtP(r.low)+'</span></td>';
    h+='<td class="'+vrelCls+'">'+fmtV(r.vol)+'</td>';
    h+='<td class="'+vrelCls+'">'+vrelStr+'</td>';
    h+='<td class="'+dc+'">'+fmtN(r.delta)+'</td>';
    h+='<td class="'+(r.buy_pct>60?'tp':r.sell_pct>60?'tn':'')+'">'+r.buy_pct.toFixed(0)+'/'+r.sell_pct.toFixed(0)+'</td>';
    h+='<td class="tb">'+fmtN(r.cvd)+'</td>';
    h+='<td class="'+oiCls+'" style="font-size:10px;white-space:nowrap">'+oiStr+'</td>';
    h+='<td class="'+dpCls+'">'+dpStr+'</td>';
    h+='<td>'+flags+'</td></tr>';
  });

  h+='</table></div>';
  h+='<div class="tbl-legend">';
  h+='<span><span style="color:var(--yellow)">■</span> OI Δ &gt;+0.15% posiciones nuevas entrando</span>';
  h+='<span><span style="color:var(--red)">■</span> OI Δ &lt;-0.15% cierre de posiciones</span>';
  h+='<span><span style="color:var(--blue)">■</span> VRel ≥1.5x volumen sobre promedio</span>';
  h+='<span><span style="color:var(--yellow)">■</span> VRel ≥2.5x spike de volumen</span>';
  h+='<span><span style="color:var(--green);font-weight:700">■</span> Δ% ≥+60% compra muy agresiva</span>';
  h+='<span><span style="color:rgba(0,200,120,0.6)">■</span> Δ% +30~60% compra moderada</span>';
  h+='<span><span style="color:rgba(255,77,77,0.6)">■</span> Δ% -30~-60% venta moderada</span>';
  h+='<span><span style="color:var(--red);font-weight:700">■</span> Δ% ≤-60% venta muy agresiva</span>';
  h+='<span><span style="color:var(--yellow)">■</span> ABS* = |Δ%|≥30 + OI Δ/Vol&lt;10% → absorción sin posiciones nuevas</span>';
  h+='</div></div>';

  document.getElementById('main').innerHTML=h;
}

try {
  render(parseCSV(INITIAL_CSV));
  document.getElementById('dot').className='dot';
  setUpdated();
  scheduleRefresh();
} catch(e) {
  document.getElementById('main').innerHTML='<p style="color:var(--red);padding:20px;">Error: '+e.message+'</p>';
}
</script>
</body>
</html>`;
}
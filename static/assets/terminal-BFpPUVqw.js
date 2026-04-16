import{S as L}from"./auth-C4Y_TkCR.js";/* empty css             *//* empty css                 */const C="/api",_e=200,Ie=6e4,Me=1e4,te=10,S=[{id:"time",label:"Time",defaultVisible:!0,required:!1,requiredFeature:null},{id:"sentiment",label:"Sentiment",defaultVisible:!0,required:!1,requiredFeature:"sentiment_filter"},{id:"source",label:"Source",defaultVisible:!0,required:!1,requiredFeature:null},{id:"headline",label:"Headline",defaultVisible:!0,required:!0,requiredFeature:null},{id:"summary",label:"Summary",defaultVisible:!0,required:!1,requiredFeature:null},{id:"ticker",label:"Ticker",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"confidence",label:"Confidence",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"risk",label:"Risk Level",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"tradeable",label:"Tradeable",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"}],Y="instnews_column_visibility",G="instnews_column_order",X="instnews_column_widths",ve="instnews_onboarding_done",R=60,he={news:{name:"News Focus",icon:"📰",description:"Headlines, sources, and summaries at a glance.",visibility:{time:!0,sentiment:!1,source:!0,headline:!0,summary:!0,ticker:!1,confidence:!1,risk:!1,tradeable:!1},order:["time","source","headline","summary","sentiment","ticker","confidence","risk","tradeable"]},trading:{name:"Trading View",icon:"📈",description:"Sentiment, tickers, and risk signals for active traders.",visibility:{time:!0,sentiment:!0,source:!1,headline:!0,summary:!1,ticker:!0,confidence:!0,risk:!0,tradeable:!1},order:["time","sentiment","ticker","headline","confidence","risk","tradeable","source","summary"]},full:{name:"Full Terminal",icon:"🖥️",description:"Every column enabled — maximum information density.",visibility:{time:!0,sentiment:!0,source:!0,headline:!0,summary:!0,ticker:!0,confidence:!0,risk:!0,tradeable:!0},order:["time","sentiment","source","headline","summary","ticker","confidence","risk","tradeable"]}};let n={items:[],seenIds:new Set,newIds:new Set,sources:[],stats:null,filter:{sentiment:"all",sources:new Set,query:"",dateFrom:"",dateTo:"",hideDuplicates:!1},refreshInterval:5e3,refreshTimer:null,lastRefresh:null,connected:!1,loading:!0,totalFetched:0,fetchCount:0,itemsPerSecond:0,startTime:Date.now(),sidebarOpen:!1,modalOpen:!1,detailModalOpen:!1,detailItem:null,userTier:null,userFeatures:{},soundEnabled:!1,columnVisibility:{},columnOrder:S.map(e=>e.id),columnWidths:{},columnSettingsOpen:!1,marketPrices:{},priceRefreshTimer:null,companyProfileOpen:!1,companyProfileSymbol:null,companyProfileData:null,companyProfileLoading:!1,companyProfileActiveTab:"fundamentals",companyProfileFinancials:null,companyProfileCompetitors:null,companyProfileInstitutions:null,companyProfileInsiders:null};const l=e=>document.querySelector(e),A=e=>[...document.querySelectorAll(e)];function K(e){if(!e)return"--:--:--";try{const t=new Date(e);return isNaN(t.getTime())?"--:--:--":t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"})}catch{return"--:--:--"}}function ge(e){if(!e)return"";try{const t=new Date(e),i=new Date-t;return i<0?"just now":i<6e4?`${Math.floor(i/1e3)}s ago`:i<36e5?`${Math.floor(i/6e4)}m ago`:i<864e5?`${Math.floor(i/36e5)}h ago`:`${Math.floor(i/864e5)}d ago`}catch{return""}}function Pe(e){if(!e)return!1;try{const t=new Date(e);return Date.now()-t.getTime()<Ie}catch{return!1}}function p(e){const t=document.createElement("div");return t.textContent=e,t.innerHTML}function Fe(e,t){return e?e.length>t?e.slice(0,t)+"…":e:""}function Ae(e){return e==null?"—":e>=1e12?"$"+(e/1e12).toFixed(2)+"T":e>=1e9?"$"+(e/1e9).toFixed(2)+"B":e>=1e6?"$"+(e/1e6).toFixed(2)+"M":"$"+e.toLocaleString()}async function F(){try{const e=new URLSearchParams({limit:_e});n.filter.dateFrom&&e.set("from",n.filter.dateFrom),n.filter.dateTo&&e.set("to",n.filter.dateTo);const t=await L.fetch(`${C}/news?${e}`);if(!t.ok)throw new Error(`HTTP ${t.status}`);const s=await t.json();if(n.connected=!0,n.loading=!1,n.fetchCount++,n.lastRefresh=new Date().toISOString(),s.items&&s.items.length>0){const i=new Set;for(const r of s.items)n.seenIds.has(r.id)||(i.add(r.id),n.seenIds.add(r.id));n.soundEnabled&&i.size>0&&n.fetchCount>1&&Oe(),n.newIds=i,n.items=s.items,n.totalFetched=s.count;const a=(Date.now()-n.startTime)/1e3;n.itemsPerSecond=a>0?(n.totalFetched/a).toFixed(1):0}T(),tt(),re(!0),J()}catch{n.connected=!1,n.loading=!1,re(!1),n.items.length===0&&Ke("Unable to connect to API. Retrying...")}}async function se(){try{const e=await L.fetch(`${C}/sources`);if(!e.ok)return;const t=await e.json();n.sources=t.sources||[],xe()}catch{}}async function z(){try{const e=await L.fetch(`${C}/stats`);if(!e.ok)return;n.stats=await e.json(),et()}catch{}}async function J(){if(!n.userFeatures.ai_ticker_recommendations||!n.columnVisibility.ticker)return;const e={};n.items.forEach(s=>{s.target_asset&&!e[s.target_asset]&&(e[s.target_asset]=s.asset_type||"")});const t=Object.keys(e);if(t.length!==0){for(let s=0;s<t.length;s+=te){const a=t.slice(s,s+te).map(async r=>{try{const o=e[r],c=o?`?asset_type=${encodeURIComponent(o)}`:"",u=await L.fetch(`${C}/market/${encodeURIComponent(r)}${c}`);u.ok&&(n.marketPrices[r]=await u.json())}catch{}});await Promise.all(a)}T()}}function He(){ye(),n.userFeatures.ai_ticker_recommendations&&n.columnVisibility.ticker&&(n.priceRefreshTimer=setInterval(J,Me))}function ye(){n.priceRefreshTimer&&(clearInterval(n.priceRefreshTimer),n.priceRefreshTimer=null)}async function ne(){try{const e=l("#btn-refresh");e&&(e.disabled=!0,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>Refreshing'),await L.fetch(`${C}/refresh`,{method:"POST"}),await F(),await z(),e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}catch{const e=l("#btn-refresh");e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}}function Oe(){try{const e=new(window.AudioContext||window.webkitAudioContext),t=e.createOscillator(),s=e.createGain();t.connect(s),s.connect(e.destination),t.type="sine",t.frequency.setValueAtTime(880,e.currentTime),t.frequency.setValueAtTime(1100,e.currentTime+.05),s.gain.setValueAtTime(.08,e.currentTime),s.gain.exponentialRampToValueAtTime(.001,e.currentTime+.15),t.start(e.currentTime),t.stop(e.currentTime+.15)}catch{}}function be(){return n.items.filter(e=>{if(n.filter.sentiment!=="all"&&e.sentiment_label!==n.filter.sentiment||n.filter.sources.size>0&&!n.filter.sources.has(e.source))return!1;if(n.filter.query){const t=n.filter.query.toLowerCase(),s=(e.title||"").toLowerCase().includes(t),i=(e.summary||"").toLowerCase().includes(t);if(!s&&!i)return!1}return!(n.filter.hideDuplicates&&e.duplicate)})}function De(){const e={all:0,bullish:0,bearish:0,neutral:0};for(const t of n.items)e.all++,e[t.sentiment_label]!==void 0&&e[t.sentiment_label]++;return e}function qe(){try{const t=localStorage.getItem(Y);if(t){const s=JSON.parse(t),i={};for(const a of S)i[a.id]=a.id in s?s[a.id]:a.defaultVisible;n.columnVisibility=i;return}}catch{}const e={};for(const t of S)e[t.id]=t.defaultVisible;n.columnVisibility=e}function we(){try{localStorage.setItem(Y,JSON.stringify(n.columnVisibility))}catch{}}function Ne(){try{const e=localStorage.getItem(G);if(e){const t=JSON.parse(e);if(Array.isArray(t)){const s=new Set(S.map(a=>a.id)),i=t.filter(a=>s.has(a));for(const a of S)i.includes(a.id)||i.push(a.id);n.columnOrder=i;return}}}catch{}n.columnOrder=S.map(e=>e.id)}function Q(){try{localStorage.setItem(G,JSON.stringify(n.columnOrder))}catch{}}function Re(){try{const e=localStorage.getItem(X);if(e){const t=JSON.parse(e);if(t&&typeof t=="object"){const s={};for(const i of S)i.id in t&&typeof t[i.id]=="number"&&t[i.id]>=R&&(s[i.id]=t[i.id]);n.columnWidths=s;return}}}catch{}n.columnWidths={}}function Z(){try{localStorage.setItem(X,JSON.stringify(n.columnWidths))}catch{}}function ke(){const e={};for(const t of S)e[t.id]=t;return n.columnOrder.map(t=>e[t]).filter(Boolean)}function $e(e){return!e.requiredFeature||n.userTier===null?!1:!n.userFeatures[e.requiredFeature]}function O(){return ke().filter(e=>$e(e)?!1:n.columnVisibility[e.id]!==!1)}function Be(){return localStorage.getItem(Y)!==null||localStorage.getItem(G)!==null||localStorage.getItem(X)!==null}function Ve(){return!(n.userTier!=="max"||localStorage.getItem(ve)||Be())}function ie(e){const t=he[e];t&&(n.columnVisibility={...t.visibility},n.columnOrder=[...t.order],n.columnWidths={},we(),Q(),Z(),P(),B(),T())}function ae(){try{localStorage.setItem(ve,"1")}catch{}const e=l("#onboarding-overlay");e&&e.remove()}function Ue(){if(!Ve())return;const e=document.createElement("div");e.id="onboarding-overlay",e.className="onboarding-overlay";const t=Object.entries(he).map(([i,a])=>{const r=S.filter(o=>a.visibility[o.id]).map(o=>`<span>${o.label}</span>`).join("");return`<div class="onboarding-preset" data-preset="${i}">
      <div class="onboarding-preset-icon">${a.icon}</div>
      <div class="onboarding-preset-name">${a.name}</div>
      <div class="onboarding-preset-desc">${a.description}</div>
      <div class="onboarding-preset-cols">${r}</div>
    </div>`}).join("");e.innerHTML=`<div class="onboarding-card">
    <h2>Choose Your Layout</h2>
    <p>Pick a starting layout for your terminal. You can always customize columns later.</p>
    <div class="onboarding-presets">${t}</div>
    <button class="onboarding-skip" id="onboarding-skip">Customize later</button>
  </div>`,document.body.appendChild(e),e.querySelectorAll(".onboarding-preset").forEach(i=>{i.addEventListener("click",()=>{const a=i.getAttribute("data-preset");ie(a),ae()})});const s=e.querySelector("#onboarding-skip");s&&s.addEventListener("click",()=>{ie("full"),ae()})}function P(){const e=document.querySelector(".news-table thead");if(!e)return;const t=O();e.innerHTML="<tr>"+t.map(i=>{const a=n.columnWidths[i.id],r=a?` style="width:${a}px"`:"";return`<th class="col-${i.id}" draggable="true" data-col-id="${i.id}"${r}><span class="th-drag-label">${i.label}</span><span class="col-resize-handle" data-col-id="${i.id}"></span></th>`}).join("")+"</tr>";const s=document.querySelector(".news-table");s&&(s.style.tableLayout=Object.keys(n.columnWidths).length>0?"fixed":""),We(),je()}function je(){const e=document.querySelector(".news-table thead tr");if(!e)return;const t=e.querySelectorAll("th[draggable]");let s=null;t.forEach(i=>{i.addEventListener("dragstart",a=>{if(a.target.closest(".col-resize-handle")){a.preventDefault();return}s=i,i.classList.add("th-dragging"),a.dataTransfer.effectAllowed="move",a.dataTransfer.setData("text/plain",i.dataset.colId)}),i.addEventListener("dragover",a=>{if(a.preventDefault(),a.dataTransfer.dropEffect="move",!s||i===s)return;e.querySelectorAll("th").forEach(c=>c.classList.remove("th-drag-over-left","th-drag-over-right"));const r=i.getBoundingClientRect(),o=r.left+r.width/2;a.clientX<o?i.classList.add("th-drag-over-left"):i.classList.add("th-drag-over-right")}),i.addEventListener("dragleave",()=>{i.classList.remove("th-drag-over-left","th-drag-over-right")}),i.addEventListener("drop",a=>{if(a.preventDefault(),a.stopPropagation(),!s||i===s)return;e.querySelectorAll("th").forEach(w=>w.classList.remove("th-drag-over-left","th-drag-over-right"));const r=s.dataset.colId,o=i.dataset.colId,c=[...n.columnOrder],u=c.indexOf(r),f=c.indexOf(o);if(u===-1||f===-1)return;c.splice(u,1);const h=i.getBoundingClientRect(),v=h.left+h.width/2,g=a.clientX<v?c.indexOf(o):c.indexOf(o)+1;c.splice(g,0,r),n.columnOrder=c,Q(),P(),T(),n.columnSettingsOpen&&B()}),i.addEventListener("dragend",()=>{i.classList.remove("th-dragging"),e.querySelectorAll("th").forEach(a=>a.classList.remove("th-drag-over-left","th-drag-over-right"))})})}function We(){document.querySelectorAll(".col-resize-handle").forEach(t=>{t.addEventListener("mousedown",ze),t.addEventListener("dblclick",Ye)})}function ze(e){e.preventDefault(),e.stopPropagation();const t=e.target,s=t.parentElement,i=t.dataset.colId,a=e.clientX,r=s.offsetWidth,o=document.querySelector(".news-table");o&&(o.style.tableLayout="fixed");const c=[...document.querySelectorAll(".news-table thead th")];let u=0;c.forEach(v=>{const g=v.offsetWidth;v.style.width=g+"px",u+=g}),o&&(o.style.width=u+"px"),document.body.style.cursor="col-resize",document.body.style.userSelect="none",t.classList.add("active");function f(v){const g=v.clientX-a,w=Math.max(R,r+g);s.style.width=w+"px",o&&(o.style.width=u+(w-r)+"px")}function h(v){document.removeEventListener("mousemove",f),document.removeEventListener("mouseup",h),document.body.style.cursor="",document.body.style.userSelect="",t.classList.remove("active"),c.forEach(w=>{const E=w.dataset.colId;E&&(n.columnWidths[E]=w.offsetWidth)});const g=v.clientX-a;n.columnWidths[i]=Math.max(R,r+g),o&&(o.style.width=""),Z(),P(),T()}document.addEventListener("mousemove",f),document.addEventListener("mouseup",h)}function Ye(e){e.preventDefault(),e.stopPropagation();const t=e.target.dataset.colId,i=O().findIndex(f=>f.id===t);if(i===-1)return;const a=document.querySelectorAll("#news-body tr");let r=R;const o=e.target.parentElement,c=document.createElement("span");c.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;",c.textContent=o.textContent,document.body.appendChild(c),r=Math.max(r,c.offsetWidth+32),document.body.removeChild(c),a.forEach(f=>{if(f.classList.contains("skeleton-row"))return;const v=f.querySelectorAll("td")[i];if(!v)return;const g=document.createElement("div");g.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:12px;",g.innerHTML=v.innerHTML,document.body.appendChild(g),r=Math.max(r,g.offsetWidth+24),document.body.removeChild(g)}),r=Math.min(r,600);const u=document.querySelector(".news-table");u&&(u.style.tableLayout="fixed"),n.columnWidths[t]=r,Z(),P(),T()}function Ge(e,t,s,i){switch(e){case"time":return`<td class="cell-time" title="${ge(t.published)}">${K(t.published)}</td>`;case"sentiment":return`<td class="cell-sentiment"><span class="sentiment-badge ${t.sentiment_label}"><span class="sentiment-dot"></span>${t.sentiment_label}</span></td>`;case"source":return`<td class="cell-source"><span class="source-tag">${p(t.source||"")}</span></td>`;case"headline":return`<td class="cell-headline"><a href="${p(t.link||"#")}" target="_blank" rel="noopener noreferrer">${p(t.title||"Untitled")}</a>${s?'<span class="badge-new">NEW</span>':""}${i}</td>`;case"summary":return`<td class="cell-summary">${p(Fe(t.summary,120))}</td>`;case"ticker":{if(!t.target_asset)return'<td class="cell-ticker"><span class="cell-dash">—</span></td>';const a=p(t.target_asset),r=n.marketPrices[t.target_asset];let o="",c="";if(r){const u=r.market_status;if(u==="24h"?c='<span class="market-dot market-dot-24h" title="24H Futures"></span>':u==="open"?c='<span class="market-dot market-dot-open" title="Market Open"></span>':c='<span class="market-dot market-dot-closed" title="Market Closed"></span>',r.price!=null){const f=r.change_percent||0,h=f>=0?"+":"",v=f>0?"price-up":f<0?"price-down":"price-flat";u==="closed"?o=`<span class="ticker-price ${v}">$${r.price.toFixed(2)} <span class="ticker-change">${h}${f.toFixed(2)}%</span><span class="market-label-closed">Closed</span></span>`:u==="24h"?o=`<span class="ticker-price ${v}">$${r.price.toFixed(2)} <span class="ticker-change">${h}${f.toFixed(2)}%</span><span class="market-label-24h">24H</span></span>`:o=`<span class="ticker-price ${v}">$${r.price.toFixed(2)} <span class="ticker-change">${h}${f.toFixed(2)}%</span></span>`}}return`<td class="cell-ticker"><span class="ticker-badge" data-ticker="${a}">${c}${a}${o}</span></td>`}case"confidence":return`<td class="cell-confidence">${t.confidence!=null?Math.round(t.confidence*100)+"%":'<span class="cell-dash">—</span>'}</td>`;case"risk":{if(!t.risk_level)return'<td class="cell-risk"><span class="cell-dash">—</span></td>';const a=t.risk_level.toLowerCase();return`<td class="cell-risk"><span class="risk-badge ${a==="low"?"green":a==="high"?"red":"yellow"}">${p(t.risk_level.toUpperCase())}</span></td>`}case"tradeable":return t.tradeable==null?'<td class="cell-tradeable"><span class="cell-dash">—</span></td>':`<td class="cell-tradeable"><span class="tradeable-badge ${t.tradeable?"yes":"no"}">${t.tradeable?"YES":"NO"}</span></td>`;default:return"<td></td>"}}function oe(e){const t=typeof e=="boolean"?e:!n.columnSettingsOpen;n.columnSettingsOpen=t;const s=l("#column-settings-panel");s&&s.classList.toggle("open",t)}function B(){const e=l("#column-settings-panel");if(!e)return;const s=ke().map(o=>{const c=$e(o),u=!c&&n.columnVisibility[o.id]!==!1,f=o.required||c;return`<div class="col-toggle-item${c?" locked":""}${o.required?" required":""}" draggable="true" data-col-id="${o.id}">
      <span class="col-drag-handle" aria-label="Drag to reorder">≡</span>
      <span class="col-toggle-label">
        ${c?'<svg class="col-lock-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>':""}
        ${p(o.label)}
      </span>
      <label class="col-toggle-switch${f?" disabled":""}">
        <input type="checkbox" ${u?"checked":""} ${f?"disabled":""} data-col-id="${o.id}">
        <span class="col-toggle-track"><span class="col-toggle-thumb"></span></span>
      </label>
    </div>`});e.innerHTML=`<div class="col-settings-header"><span>Columns</span></div>
    <div class="col-settings-list">${s.join("")}</div>`,e.querySelectorAll('input[type="checkbox"]').forEach(o=>{o.addEventListener("change",c=>{const u=c.target.dataset.colId;n.columnVisibility[u]=c.target.checked,we(),P(),T()})});const i=e.querySelector(".col-settings-list");let a=null,r=!1;i.querySelectorAll(".col-drag-handle").forEach(o=>{o.addEventListener("mousedown",()=>{r=!0})}),document.addEventListener("mouseup",()=>{r=!1},{once:!1}),i.querySelectorAll(".col-toggle-item[draggable]").forEach(o=>{o.addEventListener("dragstart",c=>{if(!r){c.preventDefault();return}a=o,n._dragging=!0,o.classList.add("dragging"),c.dataTransfer.effectAllowed="move",c.dataTransfer.setData("text/plain",o.dataset.colId)}),o.addEventListener("dragover",c=>{if(c.preventDefault(),c.dataTransfer.dropEffect="move",!a||o===a)return;i.querySelectorAll(".col-toggle-item").forEach(h=>h.classList.remove("drag-over-above","drag-over-below"));const u=o.getBoundingClientRect(),f=u.top+u.height/2;c.clientY<f?o.classList.add("drag-over-above"):o.classList.add("drag-over-below")}),o.addEventListener("dragleave",()=>{o.classList.remove("drag-over-above","drag-over-below")}),o.addEventListener("drop",c=>{if(c.preventDefault(),c.stopPropagation(),!a||o===a)return;i.querySelectorAll(".col-toggle-item").forEach(v=>v.classList.remove("drag-over-above","drag-over-below"));const u=o.getBoundingClientRect(),f=u.top+u.height/2;c.clientY<f?i.insertBefore(a,o):i.insertBefore(a,o.nextSibling);const h=[...i.querySelectorAll(".col-toggle-item[data-col-id]")].map(v=>v.dataset.colId);n.columnOrder=h,Q(),P(),T()}),o.addEventListener("dragend",()=>{o.classList.remove("dragging"),n._dragging=!1,i.querySelectorAll(".col-toggle-item").forEach(c=>c.classList.remove("drag-over-above","drag-over-below"))})}),i.addEventListener("dragover",o=>{o.preventDefault()})}function T(){const e=l("#news-body");if(!e)return;const t=be(),s=O(),i=s.length;if(t.length===0&&!n.loading){e.innerHTML=`
      <tr>
        <td colspan="${i}">
          <div class="empty-state">
            <div class="icon">◇</div>
            <div>No items match current filters</div>
            <div style="font-size:11px">Try adjusting sentiment or source filters</div>
          </div>
        </td>
      </tr>`;return}const a=t.map(r=>{const o=n.newIds.has(r.id),c=Pe(r.fetched_at),u=o?"news-row-new":"",f=r.duplicate?'<span class="badge-dup">DUP</span>':"",h=s.map(v=>Ge(v.id,r,c,f)).join("");return`<tr class="${u}" data-id="${r.id}">${h}</tr>`});e.innerHTML=a.join(""),Qe(),Ze()}function Xe(){const e=l("#news-body");if(!e)return;const t=O(),s=Array.from({length:15},()=>`<tr class="skeleton-row">${t.map(a=>`<td><div class="skeleton-block" style="width:${a.id==="headline"?200+Math.random()*200:a.id==="summary"?100+Math.random()*100:50+Math.random()*30}px"></div></td>`).join("")}</tr>`);e.innerHTML=s.join("")}function Ke(e){const t=l("#news-body");if(!t)return;const s=O().length;t.innerHTML=`
    <tr>
      <td colspan="${s}">
        <div class="loading-state">
          <div class="loading-spinner"></div>
          <div>${p(e)}</div>
        </div>
      </td>
    </tr>`}function xe(){const e=l("#source-list");if(e){if(n.sources.length)e.innerHTML=n.sources.map(t=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${t.name}">
        <span>${t.name.replace(/_/g," ")}</span>
        <span class="source-count">${t.total_items}</span>
      </label>`).join("");else{const t=["CNBC","CNBC_World","Reuters_Business","MarketWatch","MarketWatch_Markets","Investing_com","Yahoo_Finance","Nasdaq","SeekingAlpha","Benzinga","AP_News","Bloomberg_Business","Bloomberg_Markets","BBC_Business","Google_News_Business"];e.innerHTML=t.map(s=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${s}">
        <span>${s.replace(/_/g," ")}</span>
        <span class="source-count">--</span>
      </label>`).join("")}e.querySelectorAll('input[type="checkbox"]').forEach(t=>{t.addEventListener("change",()=>{Je(),T()})})}}function Je(){const e=new Set,t=[];A('#source-list input[type="checkbox"]').forEach(s=>{s.checked?t.push(s.dataset.source):e.add(s.dataset.source)}),e.size===0?n.filter.sources=new Set:n.filter.sources=new Set(t)}function Qe(){const e=De(),t={all:l("#sentiment-count-all"),bullish:l("#sentiment-count-bullish"),bearish:l("#sentiment-count-bearish"),neutral:l("#sentiment-count-neutral")};Object.entries(t).forEach(([s,i])=>{i&&(i.textContent=e[s]||0)})}function Ze(){const e=l("#total-items");if(e){const t=be();e.textContent=t.length}}function et(){if(!n.stats)return;const e=l("#total-items");e&&n.filter.sentiment==="all"&&n.filter.sources.size===0&&!n.filter.query&&(e.textContent=n.stats.total_items);const t=l("#feed-count");t&&(t.textContent=n.stats.feed_count);const s=l("#avg-sentiment");if(s){const i=n.stats.avg_sentiment_score;s.textContent=(i>=0?"+":"")+i.toFixed(3),s.style.color=i>.05?"var(--green)":i<-.05?"var(--red)":"var(--yellow)"}}function re(e){const t=l("#connection-dot"),s=l("#connection-label");t&&(t.className=e?"status-dot connected":"status-dot disconnected"),s&&(s.textContent=e?"LIVE":"DISCONNECTED")}function tt(){const e=l("#last-refresh");e&&n.lastRefresh&&(e.textContent=K(n.lastRefresh));const t=l("#items-per-sec");t&&(t.textContent=n.itemsPerSecond)}function le(){const e=l("#clock");if(!e)return;const t=new Date,s=t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"}),i=t.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric",year:"numeric"});e.textContent=`${i}  ${s}`}function Le(){Te(),n.refreshTimer=setInterval(()=>{F()},n.refreshInterval)}function Te(){n.refreshTimer&&(clearInterval(n.refreshTimer),n.refreshTimer=null)}function st(){A(".sentiment-filter-btn").forEach(d=>{d.addEventListener("click",()=>{const b=d.dataset.sentiment;n.filter.sentiment=b,A(".sentiment-filter-btn").forEach($=>$.classList.remove("active")),d.classList.add("active"),T()})});const e=l("#search-input");if(e){let d;e.addEventListener("input",b=>{clearTimeout(d),d=setTimeout(()=>{n.filter.query=b.target.value.trim(),T()},150)})}const t=l("#date-from"),s=l("#date-to");t&&t.addEventListener("change",d=>{n.filter.dateFrom=d.target.value,F()}),s&&s.addEventListener("change",d=>{n.filter.dateTo=d.target.value,F()});const i=l("#btn-clear-dates");i&&i.addEventListener("click",()=>{n.filter.dateFrom="",n.filter.dateTo="",t&&(t.value=""),s&&(s.value=""),F()});const a=l("#hide-duplicates");a&&a.addEventListener("change",d=>{n.filter.hideDuplicates=d.target.checked,T()});const r=l("#btn-refresh");r&&r.addEventListener("click",ne);const o=l("#refresh-interval");o&&o.addEventListener("change",d=>{n.refreshInterval=parseInt(d.target.value,10),Le()});const c=l("#btn-docs");c&&c.addEventListener("click",()=>N(!0));const u=l("#modal-close");u&&u.addEventListener("click",()=>N(!1));const f=l("#modal-overlay");f&&f.addEventListener("click",d=>{d.target===f&&N(!1)});const h=l("#btn-col-settings");h&&h.addEventListener("click",d=>{d.stopPropagation(),oe(),n.columnSettingsOpen&&B()}),document.addEventListener("click",d=>{n._dragging||n.columnSettingsOpen&&!d.target.closest("#column-settings-wrap")&&oe(!1)});const v=l("#news-body");v&&v.addEventListener("click",d=>{if(d.target.closest("a"))return;const b=d.target.closest(".ticker-badge[data-ticker]");if(b){d.stopPropagation(),Ce(b.dataset.ticker);return}const $=d.target.closest("tr[data-id]");if(!$)return;const D=$.dataset.id,V=n.items.find(ee=>String(ee.id)===D);V&&nt(V)});const g=l("#detail-modal-close");g&&g.addEventListener("click",j);const w=l("#detail-modal-overlay");w&&w.addEventListener("click",d=>{d.target===w&&j()});const E=l("#company-profile-close");E&&E.addEventListener("click",W);const _=l("#company-profile-overlay");_&&_.addEventListener("click",d=>{d.target===_&&W()});const I=document.querySelectorAll(".cp-tab");I.forEach(d=>{d.addEventListener("click",()=>{const b=d.dataset.tab;b!==n.companyProfileActiveTab&&(n.companyProfileActiveTab=b,I.forEach($=>$.classList.toggle("active",$.dataset.tab===b)),b==="fundamentals"&&n.companyProfileData?Ee(n.companyProfileData):b==="financials"?it(n.companyProfileSymbol):b==="competitors"?at(n.companyProfileSymbol):b==="institutions"?ot(n.companyProfileSymbol):b==="insiders"&&rt(n.companyProfileSymbol))})});const y=l("#btn-sound");y&&y.addEventListener("click",()=>{n.soundEnabled=!n.soundEnabled,y.classList.toggle("active",n.soundEnabled),y.title=n.soundEnabled?"Sound alerts ON":"Sound alerts OFF";const d=y.querySelector(".sound-icon");d&&(d.innerHTML=n.soundEnabled?'<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>':'<path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>')});const x=l("#hamburger-btn");x&&x.addEventListener("click",U);const m=l("#sidebar-backdrop");m&&m.addEventListener("click",()=>U(!1)),document.addEventListener("keydown",d=>{if(d.target.tagName==="INPUT"||d.target.tagName==="TEXTAREA"||d.target.tagName==="SELECT"){d.key==="Escape"&&d.target.blur();return}switch(d.key.toLowerCase()){case"r":d.preventDefault(),ne();break;case"f":d.preventDefault();const b=l("#search-input");b&&b.focus();break;case"1":d.preventDefault(),q("all");break;case"2":d.preventDefault(),q("bullish");break;case"3":d.preventDefault(),q("bearish");break;case"4":d.preventDefault(),q("neutral");break;case"escape":n.companyProfileOpen?W():n.detailModalOpen?j():n.modalOpen&&N(!1),n.sidebarOpen&&U(!1);break}});const k=l("#api-url");k&&k.addEventListener("click",()=>{const d=`${C}/news`;navigator.clipboard&&navigator.clipboard.writeText(d).then(()=>{k.textContent="Copied!",setTimeout(()=>{k.textContent=`${C}/news`},1500)})})}function q(e){n.filter.sentiment=e,A(".sentiment-filter-btn").forEach(t=>{t.classList.toggle("active",t.dataset.sentiment===e)}),T()}function U(e){const t=typeof e=="boolean"?e:!n.sidebarOpen;n.sidebarOpen=t;const s=l(".sidebar"),i=l("#sidebar-backdrop");s&&s.classList.toggle("open",t),i&&i.classList.toggle("open",t)}function N(e){n.modalOpen=e;const t=l("#modal-overlay");t&&t.classList.toggle("open",e),e&&A(".api-base-url").forEach(s=>{s.textContent=window.location.origin+window.location.pathname.replace(/\/[^/]*$/,"")})}function nt(e){n.detailItem=e,n.detailModalOpen=!0;const t=l("#detail-modal-overlay");if(!t)return;const s=n.userTier==="max";let i="";if(i+=`<div class="detail-article">
    <h3 class="detail-headline">${p(e.title||"Untitled")}</h3>
    <div class="detail-meta">
      <span class="source-tag">${p(e.source||"")}</span>
      <span class="detail-time">${K(e.published)} · ${ge(e.published)}</span>
    </div>
  </div>`,!s)i+=`<div class="detail-upgrade">
      <div class="detail-upgrade-icon">◇</div>
      <h4>Ticker Recommendations</h4>
      <p>Upgrade to Max to see AI ticker recommendations, risk assessment, and trading signals for every article.</p>
      <a href="/pricing" class="detail-upgrade-btn">Upgrade to Max</a>
    </div>`;else if(!e.ai_analyzed)i+=`<div class="detail-pending">
      <div class="detail-pending-icon">◇</div>
      <p>Analysis pending</p>
      <span>AI analysis has not yet been run on this article.</span>
    </div>`;else if(!e.target_asset)i+=`<div class="detail-pending">
      <div class="detail-pending-icon">—</div>
      <p>No recommendation</p>
      <span>AI analysis did not identify a tradeable ticker for this article.</span>
    </div>`;else{const r=e.confidence!=null?Math.round(e.confidence*100):"—",o=(e.risk_level||"").toLowerCase(),c=o==="low"?"green":o==="high"?"red":"yellow",u=e.tradeable?"YES":"NO",f=e.tradeable?"yes":"no",h=(e.sentiment_label||"neutral").toLowerCase(),v=e.sentiment_score!=null?(e.sentiment_score>=0?"+":"")+Number(e.sentiment_score).toFixed(2):"—";i+=`<div class="detail-ticker-header">
      <div class="detail-ticker-symbol">${p(e.target_asset)}</div>
      <span class="detail-asset-type">${p(e.asset_type||"—")}</span>
    </div>
    <div class="detail-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Sentiment</div>
        <div class="detail-metric-value">
          <span class="sentiment-badge ${h}"><span class="sentiment-dot"></span>${h}</span>
          <span class="detail-metric-sub">${v}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Confidence</div>
        <div class="detail-metric-value detail-confidence">${r}%</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Risk Level</div>
        <div class="detail-metric-value">
          <span class="detail-risk ${c}">${p((e.risk_level||"—").toUpperCase())}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Tradeable</div>
        <div class="detail-metric-value">
          <span class="detail-tradeable ${f}">${u}</span>
        </div>
      </div>
    </div>
    <div class="detail-reasoning">
      <div class="detail-reasoning-label">Reasoning</div>
      <div class="detail-reasoning-text">${p(e.reasoning||"No reasoning provided.")}</div>
    </div>`}const a=t.querySelector(".detail-modal-body");a&&(a.innerHTML=i),t.classList.add("open")}function j(){n.detailModalOpen=!1,n.detailItem=null;const e=l("#detail-modal-overlay");e&&e.classList.remove("open")}async function Ce(e){n.companyProfileOpen=!0,n.companyProfileSymbol=e,n.companyProfileData=null,n.companyProfileLoading=!0,n.companyProfileActiveTab="fundamentals",n.companyProfileFinancials=null,n.companyProfileCompetitors=null,n.companyProfileInstitutions=null,n.companyProfileInsiders=null,document.querySelectorAll(".cp-tab").forEach(a=>{a.classList.toggle("active",a.dataset.tab==="fundamentals")});const t=l("#company-profile-overlay");if(!t)return;const s=l("#company-profile-title");s&&(s.textContent=`// ${e.toUpperCase()}`);const i=l("#company-profile-body");i&&(i.innerHTML=`<div class="cp-loading">
      <div class="cp-loading-row"><div class="skeleton" style="width:60%;height:24px"></div></div>
      <div class="cp-loading-row"><div class="skeleton" style="width:40%;height:16px"></div></div>
      <div class="cp-loading-row" style="margin-top:16px"><div class="skeleton" style="width:100%;height:80px"></div></div>
      <div class="cp-loading-grid">
        <div class="skeleton" style="width:100%;height:64px"></div>
        <div class="skeleton" style="width:100%;height:64px"></div>
      </div>
    </div>`),t.classList.add("open");try{const a=await L.fetch(`${C}/market/${encodeURIComponent(e)}/details`);if(!a.ok){const o=await a.json().catch(()=>({}));throw new Error(o.message||`HTTP ${a.status}`)}const r=await a.json();n.companyProfileData=r,n.companyProfileLoading=!1,Ee(r)}catch(a){n.companyProfileLoading=!1,logger.warn("Error fetching company details for",e,a),i&&(i.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load company details for <strong>${p(e)}</strong></p>
        <span>${p(a.message)}</span>
      </div>`)}}function Ee(e){const t=l("#company-profile-body");if(!t)return;const s=e.logo_url?`<img class="cp-logo" src="${p(e.logo_url)}" alt="${p(e.name)}" onerror="this.style.display='none'">`:"",i=e.homepage_url?`<a class="cp-homepage" href="${p(e.homepage_url)}" target="_blank" rel="noopener noreferrer">${p(e.homepage_url.replace(/^https?:\/\//,""))}</a>`:"";t.innerHTML=`
    <div class="cp-header">
      ${s}
      <div class="cp-header-info">
        <div class="cp-name">${p(e.name||"—")}</div>
        <div class="cp-symbol-row">
          <span class="cp-symbol">${p(e.symbol||"—")}</span>
          ${e.sector?`<span class="cp-sector">${p(e.sector)}</span>`:""}
        </div>
      </div>
    </div>
    <div class="cp-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Market Cap</div>
        <div class="detail-metric-value">${Ae(e.market_cap)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Sector</div>
        <div class="detail-metric-value" style="font-size:12px">${p(e.sector||"—")}</div>
      </div>
    </div>
    ${e.description?`<div class="cp-description">
      <div class="cp-desc-label">About</div>
      <p class="cp-desc-text">${p(e.description)}</p>
    </div>`:""}
    ${i?`<div class="cp-links">${i}</div>`:""}
  `}function W(){n.companyProfileOpen=!1,n.companyProfileSymbol=null,n.companyProfileData=null,n.companyProfileLoading=!1,n.companyProfileActiveTab="fundamentals",n.companyProfileFinancials=null,n.companyProfileCompetitors=null,n.companyProfileInstitutions=null,n.companyProfileInsiders=null;const e=l("#company-profile-overlay");e&&e.classList.remove("open")}async function it(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileFinancials){ce(n.companyProfileFinancials);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:60%;height:24px"></div></div>
    <div class="cp-loading-grid">
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
    </div>
    <div class="cp-loading-row" style="margin-top:16px"><div class="skeleton" style="width:100%;height:120px"></div></div>
  </div>`;try{const s=await L.fetch(`${C}/market/${encodeURIComponent(e)}/financials`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileFinancials=i,n.companyProfileActiveTab==="financials"&&ce(i)}catch(s){logger.warn("Error fetching financials for",e,s),n.companyProfileActiveTab==="financials"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load financial data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function H(e){if(e==null)return"—";const t=Math.abs(e),s=e<0?"-":"";return t>=1e12?s+"$"+(t/1e12).toFixed(2)+"T":t>=1e9?s+"$"+(t/1e9).toFixed(2)+"B":t>=1e6?s+"$"+(t/1e6).toFixed(2)+"M":t>=1e3?s+"$"+(t/1e3).toFixed(2)+"K":s+"$"+t.toFixed(2)}function ce(e){const t=l("#company-profile-body");if(!t)return;const s=e.financials,i=e.earnings||[],a=s&&(s.revenue!=null||s.net_income!=null||s.eps!=null),r=i.length>0&&i.some(f=>f.actual_eps!=null);if(!a&&!r){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No financial data available</p>
      <span>Financial data is not available for this ticker (e.g., ETFs, indices).</span>
    </div>`;return}const o=s&&s.fiscal_period&&s.fiscal_year?`${s.fiscal_period} ${s.fiscal_year}`:"",c=a?`
    ${o?`<div class="cp-fin-period">Latest Quarter: ${p(o)}</div>`:""}
    <div class="cp-fin-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Revenue</div>
        <div class="detail-metric-value">${H(s.revenue)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Net Income</div>
        <div class="detail-metric-value">${H(s.net_income)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">EPS</div>
        <div class="detail-metric-value">${s.eps!=null?"$"+s.eps.toFixed(2):"—"}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">P/E Ratio</div>
        <div class="detail-metric-value">${s.pe_ratio!=null?s.pe_ratio.toFixed(1)+"x":"—"}</div>
      </div>
    </div>`:"";let u="";if(r){const f=[...i].reverse(),h=Math.max(...f.map(g=>Math.abs(g.actual_eps||0)),.01);u=`
    <div class="cp-fin-chart-section">
      <div class="cp-desc-label">Earnings Per Share — Last 4 Quarters</div>
      <div class="cp-bar-chart">${f.map(g=>{const w=g.actual_eps;if(w==null)return"";const E=Math.min(Math.abs(w)/h*100,100),I=w>=0?"cp-bar-positive":"cp-bar-negative",y=`${g.fiscal_period} ${String(g.fiscal_year).slice(-2)}`,x=g.estimated_eps!=null,m=x&&w>=g.estimated_eps,k=x?m?"cp-bar-beat":"cp-bar-miss":I;return`<div class="cp-bar-col">
        <div class="cp-bar-value ${k}">$${w.toFixed(2)}</div>
        <div class="cp-bar-track">
          <div class="cp-bar-fill ${k}" style="height:${E}%"></div>
        </div>
        <div class="cp-bar-label">${p(y)}</div>
        ${x?`<div class="cp-bar-est">Est: $${g.estimated_eps.toFixed(2)}</div>`:""}
      </div>`}).join("")}</div>
      <div class="cp-bar-legend">
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-positive"></span>Positive</span>
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-negative"></span>Negative</span>
      </div>
    </div>`}t.innerHTML=c+u}async function at(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileCompetitors){de(n.companyProfileCompetitors);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:50%;height:24px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
  </div>`;try{const s=await L.fetch(`${C}/market/${encodeURIComponent(e)}/competitors`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileCompetitors=i,n.companyProfileActiveTab==="competitors"&&de(i)}catch(s){logger.warn("Error fetching competitors for",e,s),n.companyProfileActiveTab==="competitors"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load competitor data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function de(e){const t=l("#company-profile-body");if(!t)return;const s=e.competitors||[];if(s.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No competitor data available</p>
      <span>Competitor information is not available for this ticker.</span>
    </div>`;return}const i=s.map(a=>{const r=a.change_percent!=null?a.change_percent:null,o=r!=null?r>=0?"positive":"negative":"",c=r!=null?`${r>=0?"+":""}${r.toFixed(2)}%`:"—",u=a.price!=null?`$${a.price.toFixed(2)}`:"—",f=H(a.market_cap),h=a.sector||"—";return`<tr class="cp-comp-row">
      <td class="cp-comp-ticker"><span class="cp-comp-ticker-link" data-ticker="${p(a.symbol)}">${p(a.symbol)}</span></td>
      <td class="cp-comp-name">${p(a.name)}</td>
      <td class="cp-comp-mcap">${f}</td>
      <td class="cp-comp-price">${u}</td>
      <td class="cp-comp-change ${o}">${c}</td>
      <td class="cp-comp-sector">${p(h)}</td>
    </tr>`}).join("");t.innerHTML=`
    <div class="cp-comp-section">
      <div class="cp-desc-label">Related Companies</div>
      <table class="cp-comp-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Company Name</th>
            <th>Market Cap</th>
            <th>Price</th>
            <th>Change%</th>
            <th>Sector</th>
          </tr>
        </thead>
        <tbody>${i}</tbody>
      </table>
    </div>`,t.querySelectorAll(".cp-comp-ticker-link[data-ticker]").forEach(a=>{a.addEventListener("click",()=>{Ce(a.dataset.ticker)})})}const ue="inst_tooltip_dismissed";function M(e){if(e==null)return"—";const t=Math.abs(e);return t>=1e9?(t/1e9).toFixed(2)+"B":t>=1e6?(t/1e6).toFixed(2)+"M":t>=1e3?(t/1e3).toFixed(1)+"K":t.toLocaleString()}async function ot(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileInstitutions){pe(n.companyProfileInstitutions);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:70%;height:20px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:50%;height:16px"></div></div>
    <div class="cp-loading-row" style="margin-top:12px"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
  </div>`;try{const s=await L.fetch(`${C}/market/${encodeURIComponent(e)}/institutions`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileInstitutions=i,n.companyProfileActiveTab==="institutions"&&pe(i)}catch(s){logger.warn("Error fetching institutions for",e,s),n.companyProfileActiveTab==="institutions"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load institutional data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function pe(e){const t=l("#company-profile-body");if(!t)return;const s=e.institutional_holders||[],i=e.major_position_changes||[];if(s.length===0&&i.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No institutional data available</p>
      <span>Institutional holdings data is not available for this ticker.</span>
    </div>`;return}const a=s.length>0?s[0].report_date:null,r=a?`<div class="cp-inst-date-banner">Holdings as of ${p(a)}</div>`:"",c=localStorage.getItem(ue)?"":`<div class="cp-inst-tooltip" id="cp-inst-tooltip">
    <div class="cp-inst-tooltip-text">
      <strong>About this data:</strong> 13F holdings are filed quarterly (up to 45 days after quarter end).
      13D/13G filings are filed in near-real-time when an investor crosses the 5% ownership threshold.
    </div>
    <button class="cp-inst-tooltip-dismiss" id="cp-inst-tooltip-dismiss">✕</button>
  </div>`;let u=0,f=0;s.forEach(m=>{m.value!=null&&(u+=m.value),m.shares_held!=null&&(f+=m.shares_held)});const h=`<div class="cp-inst-summary">
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Institutions Reporting</span>
      <span class="cp-inst-summary-value">${s.length}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Institutional Value</span>
      <span class="cp-inst-summary-value">${H(u)}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Shares Held</span>
      <span class="cp-inst-summary-value">${M(f)}</span>
    </div>
  </div>`,v=s.map(m=>{const k=M(m.shares_held),d=H(m.value),b=m.change_type||"held";let $="";return b==="new"?$='<span class="cp-inst-badge cp-inst-badge-new">NEW</span>':b==="increased"?$='<span class="cp-inst-change-up">▲</span>':b==="decreased"?$='<span class="cp-inst-change-down">▼</span>':$='<span class="cp-inst-change-flat">—</span>',`<tr class="cp-inst-row">
      <td class="cp-inst-name">${p(m.institution_name||"Unknown")}</td>
      <td class="cp-inst-shares">${k}</td>
      <td class="cp-inst-value">${d}</td>
      <td class="cp-inst-change">${$}</td>
    </tr>`}).join(""),g=s.length>0?`
    <div class="cp-inst-section">
      <div class="cp-desc-label">13F Institutional Holdings</div>
      <table class="cp-inst-table">
        <thead>
          <tr>
            <th>Institution</th>
            <th>Shares Held</th>
            <th>Value</th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>${v}</tbody>
      </table>
    </div>`:"",w=Date.now(),E=720*60*60*1e3,_=i.map(m=>{const k=m.filing_date||"",b=k&&w-new Date(k).getTime()<E?'<span class="cp-inst-badge cp-inst-badge-new">NEW</span> ':"",$=m.percent_owned!=null?m.percent_owned.toFixed(2)+"%":"—",D=m.filing_type||"";return`<tr class="cp-inst-row ${D.includes("13D")?"cp-inst-13d":"cp-inst-13g"}">
      <td class="cp-inst-filer">${b}${p(m.filer_name||"Unknown")}</td>
      <td class="cp-inst-pct">${$}</td>
      <td class="cp-inst-filing-date">${p(k)}</td>
      <td class="cp-inst-filing-type">${p(D)}</td>
    </tr>`}).join(""),I=i.length>0?`
    <div class="cp-inst-section cp-inst-positions">
      <div class="cp-desc-label">13D/13G Recent Activity</div>
      <table class="cp-inst-table">
        <thead>
          <tr>
            <th>Filer</th>
            <th>% Owned</th>
            <th>Filing Date</th>
            <th>Filing Type</th>
          </tr>
        </thead>
        <tbody>${_}</tbody>
      </table>
    </div>`:"",y='<div class="cp-inst-source">Source: SEC EDGAR (13F quarterly + 13D/13G real-time filings)</div>';t.innerHTML=r+c+h+g+I+y;const x=document.getElementById("cp-inst-tooltip-dismiss");x&&x.addEventListener("click",()=>{localStorage.setItem(ue,"1");const m=document.getElementById("cp-inst-tooltip");m&&m.remove()})}async function rt(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileInsiders){fe(n.companyProfileInsiders);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:70%;height:20px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:50%;height:16px"></div></div>
    <div class="cp-loading-row" style="margin-top:12px"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
  </div>`;try{const s=await L.fetch(`${C}/market/${encodeURIComponent(e)}/insiders`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileInsiders=i,n.companyProfileActiveTab==="insiders"&&fe(i)}catch(s){logger.warn("Error fetching insiders for",e,s),n.companyProfileActiveTab==="insiders"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load insider trading data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function fe(e){const t=l("#company-profile-body");if(!t)return;const s=e.insider_transactions||[];if(s.length===0){t.innerHTML=`<div class="cp-error">
      <div class="cp-error-icon">—</div>
      <p>No insider transaction data available for <strong>${p(e.symbol||"")}</strong></p>
    </div>`;return}const i=Date.now()-2160*60*60*1e3;let a=0,r=0,o=0,c=0;for(const y of s){if((y.filing_date?new Date(y.filing_date).getTime():0)<i)continue;const m=(y.transaction_type||"").toLowerCase(),k=Math.abs(y.total_value||0);m==="purchase"?(a+=k,o++):m==="sale"&&(r+=k,c++)}const u=a-r,f=u>0?"cp-insider-sentiment-buy":u<0?"cp-insider-sentiment-sell":"cp-insider-sentiment-neutral",h=u>0?"Net Buying":u<0?"Net Selling":"Neutral",v=u>0?"▲":u<0?"▼":"●",g=`<div class="cp-insider-sentiment ${f}">
    <div class="cp-insider-sentiment-header">
      <span class="cp-insider-sentiment-icon">${v}</span>
      <span class="cp-insider-sentiment-label">${h}</span>
      <span class="cp-insider-sentiment-period">90-day insider activity</span>
    </div>
    <div class="cp-insider-sentiment-stats">
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-buy-text">${o} buys</span>
        <span class="cp-insider-stat-amount">$${M(a)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-sell-text">${c} sells</span>
        <span class="cp-insider-stat-amount">$${M(r)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value">Net</span>
        <span class="cp-insider-stat-amount ${f}">${u>=0?"+":""}$${M(Math.abs(u))}</span>
      </div>
    </div>
  </div>`,_=`<div class="cp-insider-table-wrap">
    <table class="cp-insider-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Insider Name</th>
          <th>Title</th>
          <th>Type</th>
          <th>Shares</th>
          <th>Price</th>
          <th>Total Value</th>
          <th>Holdings After</th>
        </tr>
      </thead>
      <tbody>${[...s].sort((y,x)=>{const m=y.filing_date||"";return(x.filing_date||"").localeCompare(m)}).map(y=>{const x=(y.transaction_type||"").toLowerCase();let m="cp-insider-row-other";x==="purchase"?m="cp-insider-row-buy":x==="sale"?m="cp-insider-row-sell":x==="option exercise"&&(m="cp-insider-row-exercise");const k=y.shares!=null?M(y.shares):"—",d=y.price_per_share!=null?"$"+y.price_per_share.toFixed(2):"—",b=y.total_value!=null?"$"+M(y.total_value):"—",$=y.shares_held_after!=null?M(y.shares_held_after):"—";return`<tr class="cp-insider-row ${m}">
      <td class="cp-insider-date">${p(y.filing_date||"")}</td>
      <td class="cp-insider-name">${p(y.insider_name||"Unknown")}</td>
      <td class="cp-insider-title">${p(y.title||"")}</td>
      <td class="cp-insider-type">${p(y.transaction_type||"")}</td>
      <td class="cp-insider-shares">${k}</td>
      <td class="cp-insider-price">${d}</td>
      <td class="cp-insider-total">${b}</td>
      <td class="cp-insider-holdings">${$}</td>
    </tr>`}).join("")}</tbody>
    </table>
  </div>`,I='<div class="cp-insider-source">Source: SEC EDGAR Form 4 (filed within 2 business days of transaction)</div>';t.innerHTML=g+_+I}function lt(){if(typeof L>"u")return;L.init();const e=l("#btn-signin");e&&e.addEventListener("click",()=>{L.showAuthModal("signin")});const t=l("#btn-signout");t&&t.addEventListener("click",()=>{L.signOut()});const s=l("#btn-user"),i=l("#user-dropdown");s&&i&&(s.addEventListener("click",a=>{a.stopPropagation(),i.classList.toggle("open")}),document.addEventListener("click",()=>{i.classList.remove("open")})),L.onAuthChange(a=>{ct(a)})}function ct(e){const t=l("#btn-signin"),s=l("#user-menu");if(e){t&&(t.style.display="none"),s&&(s.style.display="flex");const i=l("#user-avatar"),a=l("#user-name"),r=l("#dropdown-email");i&&e.photoURL&&(i.src=e.photoURL,i.alt=e.displayName||""),a&&(a.textContent=e.displayName||e.email||""),r&&(r.textContent=e.email||""),dt()}else t&&(t.style.display="flex"),s&&(s.style.display="none"),Se()}async function dt(){try{const e=await L.fetch(`${C}/auth/tier`);if(!e.ok)return;const t=await e.json(),s=t.tier||"free",i=s==="plus"?"pro":s,a=t.features||{};n.userTier=i,n.userFeatures=a,B(),P(),T(),J(),He();const r=l("#tier-badge"),o=l("#dropdown-tier");if(r&&(r.textContent=i.toUpperCase(),r.className="tier-badge"+(i!=="free"?" "+i:"")),o){const c={free:"Free Plan",pro:"Pro Plan",plus:"Pro Plan"};o.textContent=c[i]||"Free Plan"}a.terminal_access===!1||i==="free"?Se():(ut(),Ue())}catch{}}function Se(){if(l("#upgrade-gate"))return;const e=document.createElement("div");e.id="upgrade-gate",e.style.cssText="position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(1,4,9,0.95);",e.innerHTML='<div style="text-align:center;max-width:420px;padding:40px;border:1px solid rgba(48,54,61,0.8);border-radius:12px;background:#0d1117;"><h2 style="color:#e6edf3;margin:0 0 12px;font-size:22px;">Upgrade to Pro</h2><p style="color:#8b949e;margin:0 0 24px;line-height:1.6;">The SIGNAL terminal requires a Pro subscription. Get full access to real-time news, sentiment analysis, and deduplication.</p><a href="/pricing" style="display:inline-block;padding:10px 28px;background:#238636;color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">View Plans</a><div style="margin-top:16px;"><a href="/" style="color:#8b949e;font-size:13px;text-decoration:underline;">Back to home</a></div></div>',document.body.appendChild(e),Te(),ye()}function ut(){const e=l("#upgrade-gate");e&&e.remove()}function me(){qe(),Ne(),Re(),P(),Xe(),xe(),st(),le(),lt(),setInterval(le,1e3),F(),z(),se(),Le(),setInterval(()=>{z(),se()},3e4)}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",me):me();document.addEventListener("DOMContentLoaded",function(){var e=document.getElementById("auth-gate"),t=document.getElementById("auth-gate-signin");function s(){typeof SignalAuth<"u"&&SignalAuth.isSignedIn()?e.classList.add("hidden"):e.classList.remove("hidden")}t&&t.addEventListener("click",function(){typeof SignalAuth<"u"&&SignalAuth.showAuthModal("signin")}),typeof SignalAuth<"u"&&SignalAuth.onAuthChange(s),setTimeout(function(){typeof SignalAuth<"u"&&(SignalAuth.onAuthChange(s),s())},500)});

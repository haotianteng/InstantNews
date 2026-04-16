import{S as w}from"./auth-C4Y_TkCR.js";/* empty css             *//* empty css                 */const T="/api",_e=200,Me=6e4,Pe=1e4,Z=10,_=[{id:"time",label:"Time",defaultVisible:!0,required:!1,requiredFeature:null},{id:"sentiment",label:"Sentiment",defaultVisible:!0,required:!1,requiredFeature:"sentiment_filter"},{id:"source",label:"Source",defaultVisible:!0,required:!1,requiredFeature:null},{id:"headline",label:"Headline",defaultVisible:!0,required:!0,requiredFeature:null},{id:"summary",label:"Summary",defaultVisible:!0,required:!1,requiredFeature:null},{id:"ticker",label:"Ticker",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"confidence",label:"Confidence",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"risk",label:"Risk Level",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"}],j="instnews_column_visibility",W="instnews_column_order",Y="instnews_column_widths",ve="instnews_onboarding_done",U=60,ge={news:{name:"News Focus",icon:"📰",description:"Headlines, sources, and summaries at a glance.",visibility:{time:!0,sentiment:!1,source:!0,headline:!0,summary:!0,ticker:!1,confidence:!1,risk:!1},order:["time","source","headline","summary","sentiment","ticker","confidence","risk"]},trading:{name:"Trading View",icon:"📈",description:"Sentiment, tickers, and risk signals for active traders.",visibility:{time:!0,sentiment:!0,source:!1,headline:!0,summary:!1,ticker:!0,confidence:!0,risk:!0},order:["time","sentiment","ticker","headline","confidence","risk","source","summary"]},full:{name:"Full Terminal",icon:"🖥️",description:"Every column enabled — maximum information density.",visibility:{time:!0,sentiment:!0,source:!0,headline:!0,summary:!0,ticker:!0,confidence:!0,risk:!0},order:["time","sentiment","source","headline","summary","ticker","confidence","risk"]}},ee={STOCK:{file:"stock.svg",fallback:"△",label:"Stock"},ETF:{file:"etf.svg",fallback:"◇",label:"ETF"},FUTURE:{file:"future.svg",fallback:"◎",label:"Futures"},CURRENCY:{file:"currency.svg",fallback:"¤",label:"Currency"},CRYPTO:{file:"crypto.svg",fallback:"₿",label:"Crypto"},BOND:{file:"bond.svg",fallback:"▬",label:"Bond"},OPTION:{file:"option.svg",fallback:"⊕",label:"Option"},"":{file:"stock.svg",fallback:"△",label:"Equity"}},Ie={CL:{name:"Crude Oil (WTI)",exchange:"NYMEX",unit:"1,000 barrels",tickSize:"$0.01",hours:"Sun–Fri 6:00pm–5:00pm ET"},NG:{name:"Natural Gas",exchange:"NYMEX",unit:"10,000 MMBtu",tickSize:"$0.001",hours:"Sun–Fri 6:00pm–5:00pm ET"},GC:{name:"Gold",exchange:"COMEX",unit:"100 troy oz",tickSize:"$0.10",hours:"Sun–Fri 6:00pm–5:00pm ET"},SI:{name:"Silver",exchange:"COMEX",unit:"5,000 troy oz",tickSize:"$0.005",hours:"Sun–Fri 6:00pm–5:00pm ET"},ES:{name:"E-mini S&P 500",exchange:"CME",unit:"$50 × index",tickSize:"$0.25",hours:"Sun–Fri 6:00pm–5:00pm ET"},NQ:{name:"E-mini Nasdaq 100",exchange:"CME",unit:"$20 × index",tickSize:"$0.25",hours:"Sun–Fri 6:00pm–5:00pm ET"},YM:{name:"E-mini Dow",exchange:"CBOT",unit:"$5 × index",tickSize:"$1.00",hours:"Sun–Fri 6:00pm–5:00pm ET"},ZB:{name:"30-Year T-Bond",exchange:"CBOT",unit:"$100,000 face",tickSize:"1/32 point",hours:"Sun–Fri 7:20pm–6:00pm ET"},ZC:{name:"Corn",exchange:"CBOT",unit:"5,000 bushels",tickSize:"$0.25/bu",hours:"Sun–Fri 7:00pm–7:45am, 8:30am–1:20pm CT"},ZW:{name:"Wheat",exchange:"CBOT",unit:"5,000 bushels",tickSize:"$0.25/bu",hours:"Sun–Fri 7:00pm–7:45am, 8:30am–1:20pm CT"},HG:{name:"Copper",exchange:"COMEX",unit:"25,000 lbs",tickSize:"$0.0005/lb",hours:"Sun–Fri 6:00pm–5:00pm ET"}};let s={items:[],seenIds:new Set,newIds:new Set,sources:[],stats:null,filter:{sentiment:"all",sources:new Set,query:"",dateFrom:"",dateTo:"",hideDuplicates:!1},refreshInterval:5e3,refreshTimer:null,lastRefresh:null,connected:!1,loading:!0,totalFetched:0,fetchCount:0,itemsPerSecond:0,startTime:Date.now(),sidebarOpen:!1,modalOpen:!1,detailModalOpen:!1,detailItem:null,userTier:null,userFeatures:{},soundEnabled:!1,columnVisibility:{},columnOrder:_.map(e=>e.id),columnWidths:{},columnSettingsOpen:!1,marketPrices:{},priceRefreshTimer:null,companyProfileOpen:!1,companyProfileSymbol:null,companyProfileData:null,companyProfileLoading:!1,companyProfileActiveTab:"fundamentals",companyProfileFinancials:null,companyProfileCompetitors:null,companyProfileInstitutions:null,companyProfileInsiders:null};const l=e=>document.querySelector(e),H=e=>[...document.querySelectorAll(e)];function G(e){if(!e)return"--:--:--";try{const t=new Date(e);return isNaN(t.getTime())?"--:--:--":t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"})}catch{return"--:--:--"}}function he(e){if(!e)return"";try{const t=new Date(e),i=new Date-t;return i<0?"just now":i<6e4?`${Math.floor(i/1e3)}s ago`:i<36e5?`${Math.floor(i/6e4)}m ago`:i<864e5?`${Math.floor(i/36e5)}h ago`:`${Math.floor(i/864e5)}d ago`}catch{return""}}function Fe(e){if(!e)return!1;try{const t=new Date(e);return Date.now()-t.getTime()<Me}catch{return!1}}function p(e){const t=document.createElement("div");return t.textContent=e,t.innerHTML}function Ae(e,t){return e?e.length>t?e.slice(0,t)+"…":e:""}function He(e){return e==null?"—":e>=1e12?"$"+(e/1e12).toFixed(2)+"T":e>=1e9?"$"+(e/1e9).toFixed(2)+"B":e>=1e6?"$"+(e/1e6).toFixed(2)+"M":"$"+e.toLocaleString()}async function F(){try{const e=new URLSearchParams({limit:_e});s.filter.dateFrom&&e.set("from",s.filter.dateFrom),s.filter.dateTo&&e.set("to",s.filter.dateTo);const t=await w.fetch(`${T}/news?${e}`);if(!t.ok)throw new Error(`HTTP ${t.status}`);const n=await t.json();if(s.connected=!0,s.loading=!1,s.fetchCount++,s.lastRefresh=new Date().toISOString(),n.items&&n.items.length>0){const i=new Set;for(const o of n.items)s.seenIds.has(o.id)||(i.add(o.id),s.seenIds.add(o.id));s.soundEnabled&&i.size>0&&s.fetchCount>1&&Re(),s.newIds=i,s.items=n.items,s.totalFetched=n.count;const a=(Date.now()-s.startTime)/1e3;s.itemsPerSecond=a>0?(s.totalFetched/a).toFixed(1):0}E(),nt(),re(!0),X()}catch{s.connected=!1,s.loading=!1,re(!1),s.items.length===0&&Je("Unable to connect to API. Retrying...")}}async function te(){try{const e=await w.fetch(`${T}/sources`);if(!e.ok)return;const t=await e.json();s.sources=t.sources||[],Ce()}catch{}}async function V(){try{const e=await w.fetch(`${T}/stats`);if(!e.ok)return;s.stats=await e.json(),tt()}catch{}}async function X(){if(!s.userFeatures.ai_ticker_recommendations||!s.columnVisibility.ticker)return;const e={};s.items.forEach(n=>{n.target_asset&&!e[n.target_asset]&&(e[n.target_asset]=n.asset_type||"")});const t=Object.keys(e);if(t.length!==0){for(let n=0;n<t.length;n+=Z){const a=t.slice(n,n+Z).map(async o=>{try{const r=e[o],c=r?`?asset_type=${encodeURIComponent(r)}`:"",u=await w.fetch(`${T}/market/${encodeURIComponent(o)}${c}`);u.ok&&(s.marketPrices[o]=await u.json())}catch{}});await Promise.all(a)}E()}}function Oe(){ye(),s.userFeatures.ai_ticker_recommendations&&s.columnVisibility.ticker&&(s.priceRefreshTimer=setInterval(X,Pe))}function ye(){s.priceRefreshTimer&&(clearInterval(s.priceRefreshTimer),s.priceRefreshTimer=null)}async function ne(){try{const e=l("#btn-refresh");e&&(e.disabled=!0,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>Refreshing'),await w.fetch(`${T}/refresh`,{method:"POST"}),await F(),await V(),e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}catch{const e=l("#btn-refresh");e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}}function Re(){try{const e=new(window.AudioContext||window.webkitAudioContext),t=e.createOscillator(),n=e.createGain();t.connect(n),n.connect(e.destination),t.type="sine",t.frequency.setValueAtTime(880,e.currentTime),t.frequency.setValueAtTime(1100,e.currentTime+.05),n.gain.setValueAtTime(.08,e.currentTime),n.gain.exponentialRampToValueAtTime(.001,e.currentTime+.15),t.start(e.currentTime),t.stop(e.currentTime+.15)}catch{}}function be(){return s.items.filter(e=>{if(s.filter.sentiment!=="all"&&e.sentiment_label!==s.filter.sentiment||s.filter.sources.size>0&&!s.filter.sources.has(e.source))return!1;if(s.filter.query){const t=s.filter.query.toLowerCase(),n=(e.title||"").toLowerCase().includes(t),i=(e.summary||"").toLowerCase().includes(t);if(!n&&!i)return!1}return!(s.filter.hideDuplicates&&e.duplicate)})}function Ne(){const e={all:0,bullish:0,bearish:0,neutral:0};for(const t of s.items)e.all++,e[t.sentiment_label]!==void 0&&e[t.sentiment_label]++;return e}function De(){try{const t=localStorage.getItem(j);if(t){const n=JSON.parse(t),i={};for(const a of _)i[a.id]=a.id in n?n[a.id]:a.defaultVisible;s.columnVisibility=i;return}}catch{}const e={};for(const t of _)e[t.id]=t.defaultVisible;s.columnVisibility=e}function $e(){try{localStorage.setItem(j,JSON.stringify(s.columnVisibility))}catch{}}function Ue(){try{const e=localStorage.getItem(W);if(e){const t=JSON.parse(e);if(Array.isArray(t)){const n=new Set(_.map(a=>a.id)),i=t.filter(a=>n.has(a));for(const a of _)i.includes(a.id)||i.push(a.id);s.columnOrder=i;return}}}catch{}s.columnOrder=_.map(e=>e.id)}function K(){try{localStorage.setItem(W,JSON.stringify(s.columnOrder))}catch{}}function qe(){try{const e=localStorage.getItem(Y);if(e){const t=JSON.parse(e);if(t&&typeof t=="object"){const n={};for(const i of _)i.id in t&&typeof t[i.id]=="number"&&t[i.id]>=U&&(n[i.id]=t[i.id]);s.columnWidths=n;return}}}catch{}s.columnWidths={}}function J(){try{localStorage.setItem(Y,JSON.stringify(s.columnWidths))}catch{}}function we(){const e={};for(const t of _)e[t.id]=t;return s.columnOrder.map(t=>e[t]).filter(Boolean)}function ke(e){return!e.requiredFeature||s.userTier===null?!1:!s.userFeatures[e.requiredFeature]}function R(){return we().filter(e=>ke(e)?!1:s.columnVisibility[e.id]!==!1)}function Be(){return localStorage.getItem(j)!==null||localStorage.getItem(W)!==null||localStorage.getItem(Y)!==null}function ze(){return!(s.userTier!=="max"||localStorage.getItem(ve)||Be())}function se(e){const t=ge[e];t&&(s.columnVisibility={...t.visibility},s.columnOrder=[...t.order],s.columnWidths={},$e(),K(),J(),P(),q(),E())}function ie(){try{localStorage.setItem(ve,"1")}catch{}const e=l("#onboarding-overlay");e&&e.remove()}function Ve(){if(!ze())return;const e=document.createElement("div");e.id="onboarding-overlay",e.className="onboarding-overlay";const t=Object.entries(ge).map(([i,a])=>{const o=_.filter(r=>a.visibility[r.id]).map(r=>`<span>${r.label}</span>`).join("");return`<div class="onboarding-preset" data-preset="${i}">
      <div class="onboarding-preset-icon">${a.icon}</div>
      <div class="onboarding-preset-name">${a.name}</div>
      <div class="onboarding-preset-desc">${a.description}</div>
      <div class="onboarding-preset-cols">${o}</div>
    </div>`}).join("");e.innerHTML=`<div class="onboarding-card">
    <h2>Choose Your Layout</h2>
    <p>Pick a starting layout for your terminal. You can always customize columns later.</p>
    <div class="onboarding-presets">${t}</div>
    <button class="onboarding-skip" id="onboarding-skip">Customize later</button>
  </div>`,document.body.appendChild(e),e.querySelectorAll(".onboarding-preset").forEach(i=>{i.addEventListener("click",()=>{const a=i.getAttribute("data-preset");se(a),ie()})});const n=e.querySelector("#onboarding-skip");n&&n.addEventListener("click",()=>{se("full"),ie()})}function P(){const e=document.querySelector(".news-table thead");if(!e)return;const t=R();e.innerHTML="<tr>"+t.map(i=>{const a=s.columnWidths[i.id],o=a?` style="width:${a}px"`:"";return`<th class="col-${i.id}" draggable="true" data-col-id="${i.id}"${o}><span class="th-drag-label">${i.label}</span><span class="col-resize-handle" data-col-id="${i.id}"></span></th>`}).join("")+"</tr>";const n=document.querySelector(".news-table");n&&(n.style.tableLayout=Object.keys(s.columnWidths).length>0?"fixed":""),We(),je()}function je(){const e=document.querySelector(".news-table thead tr");if(!e)return;const t=e.querySelectorAll("th[draggable]");let n=null;t.forEach(i=>{i.addEventListener("dragstart",a=>{if(a.target.closest(".col-resize-handle")){a.preventDefault();return}n=i,i.classList.add("th-dragging"),a.dataTransfer.effectAllowed="move",a.dataTransfer.setData("text/plain",i.dataset.colId)}),i.addEventListener("dragover",a=>{if(a.preventDefault(),a.dataTransfer.dropEffect="move",!n||i===n)return;e.querySelectorAll("th").forEach(c=>c.classList.remove("th-drag-over-left","th-drag-over-right"));const o=i.getBoundingClientRect(),r=o.left+o.width/2;a.clientX<r?i.classList.add("th-drag-over-left"):i.classList.add("th-drag-over-right")}),i.addEventListener("dragleave",()=>{i.classList.remove("th-drag-over-left","th-drag-over-right")}),i.addEventListener("drop",a=>{if(a.preventDefault(),a.stopPropagation(),!n||i===n)return;e.querySelectorAll("th").forEach($=>$.classList.remove("th-drag-over-left","th-drag-over-right"));const o=n.dataset.colId,r=i.dataset.colId,c=[...s.columnOrder],u=c.indexOf(o),f=c.indexOf(r);if(u===-1||f===-1)return;c.splice(u,1);const m=i.getBoundingClientRect(),h=m.left+m.width/2,g=a.clientX<h?c.indexOf(r):c.indexOf(r)+1;c.splice(g,0,o),s.columnOrder=c,K(),P(),E(),s.columnSettingsOpen&&q()}),i.addEventListener("dragend",()=>{i.classList.remove("th-dragging"),e.querySelectorAll("th").forEach(a=>a.classList.remove("th-drag-over-left","th-drag-over-right"))})})}function We(){document.querySelectorAll(".col-resize-handle").forEach(t=>{t.addEventListener("mousedown",Ye),t.addEventListener("dblclick",Ge)})}function Ye(e){e.preventDefault(),e.stopPropagation();const t=e.target,n=t.parentElement,i=t.dataset.colId,a=e.clientX,o=n.offsetWidth,r=document.querySelector(".news-table");r&&(r.style.tableLayout="fixed");const c=[...document.querySelectorAll(".news-table thead th")];let u=0;c.forEach(h=>{const g=h.offsetWidth;h.style.width=g+"px",u+=g}),r&&(r.style.width=u+"px"),document.body.style.cursor="col-resize",document.body.style.userSelect="none",t.classList.add("active");function f(h){const g=h.clientX-a,$=Math.max(U,o+g);n.style.width=$+"px",r&&(r.style.width=u+($-o)+"px")}function m(h){document.removeEventListener("mousemove",f),document.removeEventListener("mouseup",m),document.body.style.cursor="",document.body.style.userSelect="",t.classList.remove("active"),c.forEach($=>{const L=$.dataset.colId;L&&(s.columnWidths[L]=$.offsetWidth)});const g=h.clientX-a;s.columnWidths[i]=Math.max(U,o+g),r&&(r.style.width=""),J(),P(),E()}document.addEventListener("mousemove",f),document.addEventListener("mouseup",m)}function Ge(e){e.preventDefault(),e.stopPropagation();const t=e.target.dataset.colId,i=R().findIndex(f=>f.id===t);if(i===-1)return;const a=document.querySelectorAll("#news-body tr");let o=U;const r=e.target.parentElement,c=document.createElement("span");c.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;",c.textContent=r.textContent,document.body.appendChild(c),o=Math.max(o,c.offsetWidth+32),document.body.removeChild(c),a.forEach(f=>{if(f.classList.contains("skeleton-row"))return;const h=f.querySelectorAll("td")[i];if(!h)return;const g=document.createElement("div");g.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:12px;",g.innerHTML=h.innerHTML,document.body.appendChild(g),o=Math.max(o,g.offsetWidth+24),document.body.removeChild(g)}),o=Math.min(o,600);const u=document.querySelector(".news-table");u&&(u.style.tableLayout="fixed"),s.columnWidths[t]=o,J(),P(),E()}function Xe(e,t,n,i){switch(e){case"time":return`<td class="cell-time" title="${he(t.published)}">${G(t.published)}</td>`;case"sentiment":return`<td class="cell-sentiment"><span class="sentiment-badge ${t.sentiment_label}"><span class="sentiment-dot"></span>${t.sentiment_label}</span></td>`;case"source":return`<td class="cell-source"><span class="source-tag">${p(t.source||"")}</span></td>`;case"headline":{const a=t.tradeable?'<span class="t-bolt"><img src="./assets/lightneingClearBG.png" alt="Tradeable"></span>':"";return`<td class="cell-headline"><a href="${p(t.link||"#")}" target="_blank" rel="noopener noreferrer">${p(t.title||"Untitled")}</a>${n?'<span class="badge-new">NEW</span>':""}${a}${i}</td>`}case"summary":return`<td class="cell-summary">${p(Ae(t.summary,120))}</td>`;case"ticker":{if(!t.target_asset)return'<td class="cell-ticker"><span class="cell-dash">—</span></td>';const a=p(t.target_asset),o=(t.asset_type||"").toUpperCase(),r=ee[o]||ee[""],c=s.marketPrices[t.target_asset];let u="";if(c&&c.price!=null&&c.price>0){const f=c.change_percent||0,m=f>=0?"+":"",h=f>0?"price-up":f<0?"price-down":"price-flat",g=c.market_status,$=g==="closed"?'<span class="market-label-closed">Closed</span>':g==="24h"?'<span class="market-label-24h">24H</span>':"";u=`<span class="ticker-price ${h}">$${c.price.toFixed(2)} <span class="ticker-change">${m}${f.toFixed(2)}%</span>${$}</span>`}return`<td class="cell-ticker"><span class="ticker-badge" data-ticker="${a}" data-asset-type="${p(o)}"><span class="asset-icon" title="${p(r.label)}"><img src="./assets/icons/${r.file}" alt="${p(r.label)}" onerror="this.parentElement.textContent='${r.fallback}'"></span>${a}${u}</span></td>`}case"confidence":return`<td class="cell-confidence">${t.confidence!=null?Math.round(t.confidence*100)+"%":'<span class="cell-dash">—</span>'}</td>`;case"risk":{if(!t.risk_level)return'<td class="cell-risk"><span class="cell-dash">—</span></td>';const a=t.risk_level.toLowerCase();return`<td class="cell-risk"><span class="risk-badge ${a==="low"?"green":a==="high"?"red":"yellow"}">${p(t.risk_level.toUpperCase())}</span></td>`}default:return"<td></td>"}}function ae(e){const t=typeof e=="boolean"?e:!s.columnSettingsOpen;s.columnSettingsOpen=t;const n=l("#column-settings-panel");n&&n.classList.toggle("open",t)}function q(){const e=l("#column-settings-panel");if(!e)return;const n=we().map(r=>{const c=ke(r),u=!c&&s.columnVisibility[r.id]!==!1,f=r.required||c;return`<div class="col-toggle-item${c?" locked":""}${r.required?" required":""}" draggable="true" data-col-id="${r.id}">
      <span class="col-drag-handle" aria-label="Drag to reorder">≡</span>
      <span class="col-toggle-label">
        ${c?'<svg class="col-lock-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg><span class="col-max-badge">MAX</span>':""}
        ${p(r.label)}
      </span>
      <label class="col-toggle-switch${f?" disabled":""}">
        <input type="checkbox" ${u?"checked":""} ${f?"disabled":""} data-col-id="${r.id}">
        <span class="col-toggle-track"><span class="col-toggle-thumb"></span></span>
      </label>
    </div>`});e.innerHTML=`<div class="col-settings-header"><span>Columns</span></div>
    <div class="col-settings-list">${n.join("")}</div>`,e.querySelectorAll('input[type="checkbox"]').forEach(r=>{r.addEventListener("change",c=>{const u=c.target.dataset.colId;s.columnVisibility[u]=c.target.checked,$e(),P(),E()})}),e.querySelectorAll(".col-toggle-item.locked").forEach(r=>{r.style.cursor="pointer",r.addEventListener("click",c=>{c.target.closest("input")||gt()})});const i=e.querySelector(".col-settings-list");let a=null,o=!1;i.querySelectorAll(".col-drag-handle").forEach(r=>{r.addEventListener("mousedown",()=>{o=!0})}),document.addEventListener("mouseup",()=>{o=!1},{once:!1}),i.querySelectorAll(".col-toggle-item[draggable]").forEach(r=>{r.addEventListener("dragstart",c=>{if(!o){c.preventDefault();return}a=r,s._dragging=!0,r.classList.add("dragging"),c.dataTransfer.effectAllowed="move",c.dataTransfer.setData("text/plain",r.dataset.colId)}),r.addEventListener("dragover",c=>{if(c.preventDefault(),c.dataTransfer.dropEffect="move",!a||r===a)return;i.querySelectorAll(".col-toggle-item").forEach(m=>m.classList.remove("drag-over-above","drag-over-below"));const u=r.getBoundingClientRect(),f=u.top+u.height/2;c.clientY<f?r.classList.add("drag-over-above"):r.classList.add("drag-over-below")}),r.addEventListener("dragleave",()=>{r.classList.remove("drag-over-above","drag-over-below")}),r.addEventListener("drop",c=>{if(c.preventDefault(),c.stopPropagation(),!a||r===a)return;i.querySelectorAll(".col-toggle-item").forEach(h=>h.classList.remove("drag-over-above","drag-over-below"));const u=r.getBoundingClientRect(),f=u.top+u.height/2;c.clientY<f?i.insertBefore(a,r):i.insertBefore(a,r.nextSibling);const m=[...i.querySelectorAll(".col-toggle-item[data-col-id]")].map(h=>h.dataset.colId);s.columnOrder=m,K(),P(),E()}),r.addEventListener("dragend",()=>{r.classList.remove("dragging"),s._dragging=!1,i.querySelectorAll(".col-toggle-item").forEach(c=>c.classList.remove("drag-over-above","drag-over-below"))})}),i.addEventListener("dragover",r=>{r.preventDefault()})}function E(){const e=l("#news-body");if(!e)return;const t=be(),n=R(),i=n.length;if(t.length===0&&!s.loading){e.innerHTML=`
      <tr>
        <td colspan="${i}">
          <div class="empty-state">
            <div class="icon">◇</div>
            <div>No items match current filters</div>
            <div style="font-size:11px">Try adjusting sentiment or source filters</div>
          </div>
        </td>
      </tr>`;return}const a=t.map(o=>{const r=s.newIds.has(o.id),c=Fe(o.fetched_at),u=r?"news-row-new":"",f=o.duplicate?'<span class="badge-dup">DUP</span>':"",m=n.map(h=>Xe(h.id,o,c,f)).join("");return`<tr class="${u}" data-id="${o.id}">${m}</tr>`});e.innerHTML=a.join(""),Ze(),et()}function Ke(){const e=l("#news-body");if(!e)return;const t=R(),n=Array.from({length:15},()=>`<tr class="skeleton-row">${t.map(a=>`<td><div class="skeleton-block" style="width:${a.id==="headline"?200+Math.random()*200:a.id==="summary"?100+Math.random()*100:50+Math.random()*30}px"></div></td>`).join("")}</tr>`);e.innerHTML=n.join("")}function Je(e){const t=l("#news-body");if(!t)return;const n=R().length;t.innerHTML=`
    <tr>
      <td colspan="${n}">
        <div class="loading-state">
          <div class="loading-spinner"></div>
          <div>${p(e)}</div>
        </div>
      </td>
    </tr>`}function Ce(){const e=l("#source-list");if(e){if(s.sources.length)e.innerHTML=s.sources.map(t=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${t.name}">
        <span>${t.name.replace(/_/g," ")}</span>
        <span class="source-count">${t.total_items}</span>
      </label>`).join("");else{const t=["CNBC","CNBC_World","Reuters_Business","MarketWatch","MarketWatch_Markets","Investing_com","Yahoo_Finance","Nasdaq","SeekingAlpha","Benzinga","AP_News","Bloomberg_Business","Bloomberg_Markets","BBC_Business","Google_News_Business"];e.innerHTML=t.map(n=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${n}">
        <span>${n.replace(/_/g," ")}</span>
        <span class="source-count">--</span>
      </label>`).join("")}e.querySelectorAll('input[type="checkbox"]').forEach(t=>{t.addEventListener("change",()=>{Qe(),E()})})}}function Qe(){const e=new Set,t=[];H('#source-list input[type="checkbox"]').forEach(n=>{n.checked?t.push(n.dataset.source):e.add(n.dataset.source)}),e.size===0?s.filter.sources=new Set:s.filter.sources=new Set(t)}function Ze(){const e=Ne(),t={all:l("#sentiment-count-all"),bullish:l("#sentiment-count-bullish"),bearish:l("#sentiment-count-bearish"),neutral:l("#sentiment-count-neutral")};Object.entries(t).forEach(([n,i])=>{i&&(i.textContent=e[n]||0)})}function et(){const e=l("#total-items");if(e){const t=be();e.textContent=t.length}}function tt(){if(!s.stats)return;const e=l("#total-items");e&&s.filter.sentiment==="all"&&s.filter.sources.size===0&&!s.filter.query&&(e.textContent=s.stats.total_items);const t=l("#feed-count");t&&(t.textContent=s.stats.feed_count);const n=l("#avg-sentiment");if(n){const i=s.stats.avg_sentiment_score;n.textContent=(i>=0?"+":"")+i.toFixed(3),n.style.color=i>.05?"var(--green)":i<-.05?"var(--red)":"var(--yellow)"}}function re(e){const t=l("#connection-dot"),n=l("#connection-label");t&&(t.className=e?"status-dot connected":"status-dot disconnected"),n&&(n.textContent=e?"LIVE":"DISCONNECTED")}function nt(){const e=l("#last-refresh");e&&s.lastRefresh&&(e.textContent=G(s.lastRefresh));const t=l("#items-per-sec");t&&(t.textContent=s.itemsPerSecond)}function oe(){const e=l("#clock");if(!e)return;const t=new Date,n=t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"}),i=t.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric",year:"numeric"});e.textContent=`${i}  ${n}`}function Te(){Ee(),s.refreshTimer=setInterval(()=>{F()},s.refreshInterval)}function Ee(){s.refreshTimer&&(clearInterval(s.refreshTimer),s.refreshTimer=null)}function st(){H(".sentiment-filter-btn").forEach(d=>{d.addEventListener("click",()=>{const b=d.dataset.sentiment;s.filter.sentiment=b,H(".sentiment-filter-btn").forEach(C=>C.classList.remove("active")),d.classList.add("active"),E()})});const e=l("#search-input");if(e){let d;e.addEventListener("input",b=>{clearTimeout(d),d=setTimeout(()=>{s.filter.query=b.target.value.trim(),E()},150)})}const t=l("#date-from"),n=l("#date-to");t&&t.addEventListener("change",d=>{s.filter.dateFrom=d.target.value,F()}),n&&n.addEventListener("change",d=>{s.filter.dateTo=d.target.value,F()});const i=l("#btn-clear-dates");i&&i.addEventListener("click",()=>{s.filter.dateFrom="",s.filter.dateTo="",t&&(t.value=""),n&&(n.value=""),F()});const a=l("#hide-duplicates");a&&a.addEventListener("change",d=>{s.filter.hideDuplicates=d.target.checked,E()});const o=l("#btn-refresh");o&&o.addEventListener("click",ne);const r=l("#refresh-interval");r&&r.addEventListener("change",d=>{s.refreshInterval=parseInt(d.target.value,10),Te()});const c=l("#btn-docs");c&&c.addEventListener("click",()=>D(!0));const u=l("#modal-close");u&&u.addEventListener("click",()=>D(!1));const f=l("#modal-overlay");f&&f.addEventListener("click",d=>{d.target===f&&D(!1)});const m=l("#btn-col-settings");m&&m.addEventListener("click",d=>{d.stopPropagation(),ae(),s.columnSettingsOpen&&q()}),document.addEventListener("click",d=>{s._dragging||s.columnSettingsOpen&&!d.target.closest("#column-settings-wrap")&&ae(!1)});const h=l("#news-body");h&&h.addEventListener("click",d=>{if(d.target.closest("a"))return;const b=d.target.closest(".ticker-badge[data-ticker]");if(b){d.stopPropagation(),xe(b.dataset.ticker,b.dataset.assetType||"");return}const C=d.target.closest("tr[data-id]");if(!C)return;const S=C.dataset.id,A=s.items.find(Q=>String(Q.id)===S);A&&it(A)});const g=l("#detail-modal-close");g&&g.addEventListener("click",z);const $=l("#detail-modal-overlay");$&&$.addEventListener("click",d=>{d.target===$&&z()});const L=document.getElementById("company-profile-close");L&&L.addEventListener("click",ce);const I=document.querySelectorAll(".cp-tab");I.forEach(d=>{d.addEventListener("click",()=>{const b=d.dataset.tab;b!==s.companyProfileActiveTab&&(s.companyProfileActiveTab=b,I.forEach(C=>C.classList.toggle("active",C.dataset.tab===b)),b==="overview"||(b==="fundamentals"&&s.companyProfileData?Se(s.companyProfileData):b==="financials"?ct(s.companyProfileSymbol):b==="competitors"?lt(s.companyProfileSymbol):b==="institutions"?dt(s.companyProfileSymbol):b==="insiders"&&pt(s.companyProfileSymbol)))})});const x=l("#btn-sound");x&&x.addEventListener("click",()=>{s.soundEnabled=!s.soundEnabled,x.classList.toggle("active",s.soundEnabled),x.title=s.soundEnabled?"Sound alerts ON":"Sound alerts OFF";const d=x.querySelector(".sound-icon");d&&(d.innerHTML=s.soundEnabled?'<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>':'<path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>')});const y=l("#hamburger-btn");y&&y.addEventListener("click",B);const k=l("#sidebar-backdrop");k&&k.addEventListener("click",()=>B(!1)),document.addEventListener("keydown",d=>{if(d.target.tagName==="INPUT"||d.target.tagName==="TEXTAREA"||d.target.tagName==="SELECT"){d.key==="Escape"&&d.target.blur();return}switch(d.key.toLowerCase()){case"r":d.preventDefault(),ne();break;case"f":d.preventDefault();const b=l("#search-input");b&&b.focus();break;case"1":d.preventDefault(),N("all");break;case"2":d.preventDefault(),N("bullish");break;case"3":d.preventDefault(),N("bearish");break;case"4":d.preventDefault(),N("neutral");break;case"escape":s.companyProfileOpen?ce():s.detailModalOpen?z():s.modalOpen&&D(!1),s.sidebarOpen&&B(!1);break}});const v=l("#api-url");v&&v.addEventListener("click",()=>{const d=`${T}/news`;navigator.clipboard&&navigator.clipboard.writeText(d).then(()=>{v.textContent="Copied!",setTimeout(()=>{v.textContent=`${T}/news`},1500)})})}function N(e){s.filter.sentiment=e,H(".sentiment-filter-btn").forEach(t=>{t.classList.toggle("active",t.dataset.sentiment===e)}),E()}function B(e){const t=typeof e=="boolean"?e:!s.sidebarOpen;s.sidebarOpen=t;const n=l(".sidebar"),i=l("#sidebar-backdrop");n&&n.classList.toggle("open",t),i&&i.classList.toggle("open",t)}function D(e){s.modalOpen=e;const t=l("#modal-overlay");t&&t.classList.toggle("open",e),e&&H(".api-base-url").forEach(n=>{n.textContent=window.location.origin+window.location.pathname.replace(/\/[^/]*$/,"")})}function it(e){s.detailItem=e,s.detailModalOpen=!0;const t=l("#detail-modal-overlay");if(!t)return;const n=s.userTier==="max";let i="";if(i+=`<div class="detail-article">
    <h3 class="detail-headline">${p(e.title||"Untitled")}</h3>
    <div class="detail-meta">
      <span class="source-tag">${p(e.source||"")}</span>
      <span class="detail-time">${G(e.published)} · ${he(e.published)}</span>
    </div>
  </div>`,!n)i+=`<div class="detail-upgrade">
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
    </div>`;else{const o=e.confidence!=null?Math.round(e.confidence*100):"—",r=(e.risk_level||"").toLowerCase(),c=r==="low"?"green":r==="high"?"red":"yellow",u=e.tradeable?"YES":"NO",f=e.tradeable?"yes":"no",m=(e.sentiment_label||"neutral").toLowerCase(),h=e.sentiment_score!=null?(e.sentiment_score>=0?"+":"")+Number(e.sentiment_score).toFixed(2):"—";i+=`<div class="detail-ticker-header">
      <div class="detail-ticker-symbol">${p(e.target_asset)}</div>
      <span class="detail-asset-type">${p(e.asset_type||"—")}</span>
    </div>
    <div class="detail-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Sentiment</div>
        <div class="detail-metric-value">
          <span class="sentiment-badge ${m}"><span class="sentiment-dot"></span>${m}</span>
          <span class="detail-metric-sub">${h}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Confidence</div>
        <div class="detail-metric-value detail-confidence">${o}%</div>
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
    </div>`}const a=t.querySelector(".detail-modal-body");a&&(a.innerHTML=i),t.classList.add("open")}function z(){s.detailModalOpen=!1,s.detailItem=null;const e=l("#detail-modal-overlay");e&&e.classList.remove("open")}async function xe(e,t=""){const n=t.toUpperCase();s.companyProfileOpen=!0,s.companyProfileSymbol=e,s.companyProfileAssetType=n,s.companyProfileData=null,s.companyProfileLoading=!0,s.companyProfileFinancials=null,s.companyProfileCompetitors=null,s.companyProfileInstitutions=null,s.companyProfileInsiders=null;const o=n==="FUTURE"||n==="CURRENCY"?["overview"]:["fundamentals","financials","competitors","institutions","insiders"],r=o[0];s.companyProfileActiveTab=r,document.querySelectorAll(".cp-tab").forEach(m=>{m.style.display=o.includes(m.dataset.tab)?"":"none",m.classList.toggle("active",m.dataset.tab===r)});const c=l("#company-profile-panel");if(!c)return;const u=l("#company-profile-title");if(u){const m=n==="FUTURE"?" FUTURES":n==="CURRENCY"?" FX":"";u.textContent=`// ${e.toUpperCase()}${m}`}const f=l("#company-profile-body");f&&(f.innerHTML=`<div class="cp-spinner-wrap">
      <div class="cp-spinner"></div>
      <span class="cp-spinner-text">Loading${n==="FUTURE"?" contract":n==="CURRENCY"?" forex":" company"} data…</span>
    </div>`),c.classList.add("open"),document.querySelector(".dashboard").classList.add("cp-open"),n==="FUTURE"?rt(e):n==="CURRENCY"?ot(e):at(e)}async function at(e){const t=l("#company-profile-body");if(t)try{const n=await w.fetch(`${T}/market/${encodeURIComponent(e)}/details`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileData=i,s.companyProfileLoading=!1,Se(i)}catch(n){s.companyProfileLoading=!1,logger.warn("Error fetching company details for",e,n),t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load company details for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}function rt(e){const t=l("#company-profile-body");if(!t)return;const n=Ie[e.toUpperCase()]||null,i=n?n.name:"Futures Contract",a=s.marketPrices[e];let o="";if(a&&a.price!=null){const c=a.change_percent||0,u=c>=0?"+":"",f=c>0?"price-up":c<0?"price-down":"price-flat";o=`
      <div class="cp-section">
        <div class="cp-section-title">CURRENT PRICE</div>
        <div class="cp-futures-price">
          <span class="cp-big-price ${f}">$${a.price.toFixed(2)}</span>
          <span class="ticker-change ${f}">${u}${c.toFixed(2)}%</span>
        </div>
      </div>`}let r="";n&&(r=`
      <div class="cp-section">
        <div class="cp-section-title">CONTRACT SPECIFICATIONS</div>
        <div class="cp-specs-grid">
          <div class="cp-spec"><span class="cp-spec-label">Exchange</span><span class="cp-spec-value">${p(n.exchange)}</span></div>
          <div class="cp-spec"><span class="cp-spec-label">Contract Unit</span><span class="cp-spec-value">${p(n.unit)}</span></div>
          <div class="cp-spec"><span class="cp-spec-label">Tick Size</span><span class="cp-spec-value">${p(n.tickSize)}</span></div>
          <div class="cp-spec"><span class="cp-spec-label">Trading Hours</span><span class="cp-spec-value">${p(n.hours)}</span></div>
        </div>
      </div>`),t.innerHTML=`
    <div class="cp-instrument-header">
      <div class="cp-instrument-icon">◎</div>
      <div>
        <div class="cp-instrument-name">${p(i)}</div>
        <div class="cp-instrument-meta">
          <span class="cp-instrument-symbol">${p(e.toUpperCase())}</span>
          <span class="cp-instrument-type">FUTURE</span>
        </div>
      </div>
    </div>
    ${o}
    ${r}`,s.companyProfileLoading=!1}async function ot(e){const t=l("#company-profile-body");if(!t)return;const n=e.toUpperCase()+"/USD";try{const i=await w.fetch(`${T}/market/forex/${encodeURIComponent(e)}`);if(!i.ok){const f=await i.json().catch(()=>({}));throw new Error(f.message||`HTTP ${i.status}`)}const a=await i.json();s.companyProfileLoading=!1;const o=a.change_percent||0,r=o>=0?"+":"",c=o>0?"price-up":o<0?"price-down":"price-flat",u=a.day_high!=null&&a.day_low!=null?`<div class="cp-section">
          <div class="cp-section-title">DAY RANGE</div>
          <div class="cp-range">${a.day_low.toFixed(4)} — ${a.day_high.toFixed(4)}</div>
        </div>`:"";t.innerHTML=`
      <div class="cp-instrument-header">
        <div class="cp-instrument-icon">¤</div>
        <div>
          <div class="cp-instrument-name">${p(n)}</div>
          <div class="cp-instrument-meta">
            <span class="cp-instrument-symbol">${p(e.toUpperCase())}</span>
            <span class="cp-instrument-type">CURRENCY</span>
          </div>
        </div>
      </div>
      <div class="cp-section">
        <div class="cp-section-title">EXCHANGE RATE</div>
        <div class="cp-futures-price">
          <span class="cp-big-price ${c}">${a.price!=null?a.price.toFixed(4):"—"}</span>
          <span class="ticker-change ${c}">${r}${o.toFixed(2)}%</span>
        </div>
      </div>
      ${u}`}catch(i){s.companyProfileLoading=!1,logger.warn("Error fetching forex data for",e,i),t.innerHTML=`<div class="cp-error">
      <div class="cp-error-icon">¤</div>
      <p>Currency data not available for <strong>${p(e.toUpperCase())}</strong></p>
      <span>${p(i.message)}</span>
    </div>`}}function Se(e){const t=l("#company-profile-body");if(!t)return;const n=e.logo_url?`<img class="cp-logo" src="${p(e.logo_url)}" alt="${p(e.name)}" onerror="this.style.display='none'">`:"",i=e.homepage_url?`<a class="cp-homepage" href="${p(e.homepage_url)}" target="_blank" rel="noopener noreferrer">${p(e.homepage_url.replace(/^https?:\/\//,""))}</a>`:"";t.innerHTML=`
    <div class="cp-header">
      ${n}
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
        <div class="detail-metric-value">${He(e.market_cap)}</div>
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
  `}function ce(){s.companyProfileOpen=!1,s.companyProfileSymbol=null,s.companyProfileData=null,s.companyProfileLoading=!1,s.companyProfileActiveTab="fundamentals",s.companyProfileFinancials=null,s.companyProfileCompetitors=null,s.companyProfileInstitutions=null,s.companyProfileInsiders=null;const e=l("#company-profile-panel");e&&e.classList.remove("open");const t=document.querySelector(".dashboard");t&&t.classList.remove("cp-open")}async function ct(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileFinancials){le(s.companyProfileFinancials);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading financials…</span>
  </div>`;try{const n=await w.fetch(`${T}/market/${encodeURIComponent(e)}/financials`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileFinancials=i,s.companyProfileActiveTab==="financials"&&le(i)}catch(n){logger.warn("Error fetching financials for",e,n),s.companyProfileActiveTab==="financials"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load financial data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function O(e){if(e==null)return"—";const t=Math.abs(e),n=e<0?"-":"";return t>=1e12?n+"$"+(t/1e12).toFixed(2)+"T":t>=1e9?n+"$"+(t/1e9).toFixed(2)+"B":t>=1e6?n+"$"+(t/1e6).toFixed(2)+"M":t>=1e3?n+"$"+(t/1e3).toFixed(2)+"K":n+"$"+t.toFixed(2)}function le(e){const t=l("#company-profile-body");if(!t)return;const n=e.financials,i=e.earnings||[],a=n&&(n.revenue!=null||n.net_income!=null||n.eps!=null),o=i.length>0&&i.some(f=>f.actual_eps!=null);if(!a&&!o){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No financial data available</p>
      <span>Financial data is not available for this ticker (e.g., ETFs, indices).</span>
    </div>`;return}const r=n&&n.fiscal_period&&n.fiscal_year?`${n.fiscal_period} ${n.fiscal_year}`:"",c=a?`
    ${r?`<div class="cp-fin-period">Latest Quarter: ${p(r)}</div>`:""}
    <div class="cp-fin-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Revenue</div>
        <div class="detail-metric-value">${O(n.revenue)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Net Income</div>
        <div class="detail-metric-value">${O(n.net_income)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">EPS</div>
        <div class="detail-metric-value">${n.eps!=null?"$"+n.eps.toFixed(2):"—"}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">P/E Ratio</div>
        <div class="detail-metric-value">${n.pe_ratio!=null?n.pe_ratio.toFixed(1)+"x":"—"}</div>
      </div>
    </div>`:"";let u="";if(o){const f=[...i].reverse(),m=Math.max(...f.map(g=>Math.abs(g.actual_eps||0)),.01);u=`
    <div class="cp-fin-chart-section">
      <div class="cp-desc-label">Earnings Per Share — Last 4 Quarters</div>
      <div class="cp-bar-chart">${f.map(g=>{const $=g.actual_eps;if($==null)return"";const L=Math.min(Math.abs($)/m*100,100),x=$>=0?"cp-bar-positive":"cp-bar-negative",y=`${g.fiscal_period} ${String(g.fiscal_year).slice(-2)}`,k=g.estimated_eps!=null,v=k&&$>=g.estimated_eps,d=k?v?"cp-bar-beat":"cp-bar-miss":x;return`<div class="cp-bar-col">
        <div class="cp-bar-value ${d}">$${$.toFixed(2)}</div>
        <div class="cp-bar-track">
          <div class="cp-bar-fill ${d}" style="height:${L}%"></div>
        </div>
        <div class="cp-bar-label">${p(y)}</div>
        ${k?`<div class="cp-bar-est">Est: $${g.estimated_eps.toFixed(2)}</div>`:""}
      </div>`}).join("")}</div>
      <div class="cp-bar-legend">
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-positive"></span>Positive</span>
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-negative"></span>Negative</span>
      </div>
    </div>`}t.innerHTML=c+u}async function lt(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileCompetitors){de(s.companyProfileCompetitors);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading competitors…</span>
  </div>`;try{const n=await w.fetch(`${T}/market/${encodeURIComponent(e)}/competitors`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileCompetitors=i,s.companyProfileActiveTab==="competitors"&&de(i)}catch(n){logger.warn("Error fetching competitors for",e,n),s.companyProfileActiveTab==="competitors"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load competitor data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function de(e){const t=l("#company-profile-body");if(!t)return;const n=e.competitors||[];if(n.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No competitor data available</p>
      <span>Competitor information is not available for this ticker.</span>
    </div>`;return}const i=n.map(a=>{const o=a.change_percent!=null?a.change_percent:null,r=o!=null?o>=0?"positive":"negative":"",c=o!=null?`${o>=0?"+":""}${o.toFixed(2)}%`:"—",u=a.price!=null?`$${a.price.toFixed(2)}`:"—",f=O(a.market_cap),m=a.sector||"—";return`<tr class="cp-comp-row">
      <td class="cp-comp-ticker"><span class="cp-comp-ticker-link" data-ticker="${p(a.symbol)}">${p(a.symbol)}</span></td>
      <td class="cp-comp-name">${p(a.name)}</td>
      <td class="cp-comp-mcap">${f}</td>
      <td class="cp-comp-price">${u}</td>
      <td class="cp-comp-change ${r}">${c}</td>
      <td class="cp-comp-sector">${p(m)}</td>
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
    </div>`,t.querySelectorAll(".cp-comp-ticker-link[data-ticker]").forEach(a=>{a.addEventListener("click",()=>{xe(a.dataset.ticker)})})}const pe="inst_tooltip_dismissed";function M(e){if(e==null)return"—";const t=Math.abs(e);return t>=1e9?(t/1e9).toFixed(2)+"B":t>=1e6?(t/1e6).toFixed(2)+"M":t>=1e3?(t/1e3).toFixed(1)+"K":t.toLocaleString()}async function dt(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileInstitutions){ue(s.companyProfileInstitutions);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading institutional data…</span>
  </div>`;try{const n=await w.fetch(`${T}/market/${encodeURIComponent(e)}/institutions`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileInstitutions=i,s.companyProfileActiveTab==="institutions"&&ue(i)}catch(n){logger.warn("Error fetching institutions for",e,n),s.companyProfileActiveTab==="institutions"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load institutional data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function ue(e){const t=l("#company-profile-body");if(!t)return;const n=e.institutional_holders||[],i=e.major_position_changes||[];if(n.length===0&&i.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No institutional data available</p>
      <span>Institutional holdings data is not available for this ticker.</span>
    </div>`;return}const a=n.length>0?n[0].report_date:null,o=a?`<div class="cp-inst-date-banner">Holdings as of ${p(a)}</div>`:"",c=localStorage.getItem(pe)?"":`<div class="cp-inst-tooltip" id="cp-inst-tooltip">
    <div class="cp-inst-tooltip-text">
      <strong>About this data:</strong> 13F holdings are filed quarterly (up to 45 days after quarter end).
      13D/13G filings are filed in near-real-time when an investor crosses the 5% ownership threshold.
    </div>
    <button class="cp-inst-tooltip-dismiss" id="cp-inst-tooltip-dismiss">✕</button>
  </div>`;let u=0,f=0;n.forEach(v=>{v.value!=null&&(u+=v.value),v.shares_held!=null&&(f+=v.shares_held)});const m=`<div class="cp-inst-summary">
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Institutions Reporting</span>
      <span class="cp-inst-summary-value">${n.length}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Institutional Value</span>
      <span class="cp-inst-summary-value">${O(u)}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Shares Held</span>
      <span class="cp-inst-summary-value">${M(f)}</span>
    </div>
  </div>`,h=n.map(v=>{const d=M(v.shares_held),b=O(v.value),C=v.change_type||"held";let S="";return C==="new"?S='<span class="cp-inst-badge cp-inst-badge-new">NEW</span>':C==="increased"?S='<span class="cp-inst-change-up">▲</span>':C==="decreased"?S='<span class="cp-inst-change-down">▼</span>':S='<span class="cp-inst-change-flat">—</span>',`<tr class="cp-inst-row">
      <td class="cp-inst-name">${p(v.institution_name||"Unknown")}</td>
      <td class="cp-inst-shares">${d}</td>
      <td class="cp-inst-value">${b}</td>
      <td class="cp-inst-change">${S}</td>
    </tr>`}).join(""),g=n.length>0?`
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
        <tbody>${h}</tbody>
      </table>
    </div>`:"",$=Date.now(),L=720*60*60*1e3,I=i.map(v=>{const d=v.filing_date||"",C=d&&$-new Date(d).getTime()<L?'<span class="cp-inst-badge cp-inst-badge-new">NEW</span> ':"",S=v.percent_owned!=null?v.percent_owned.toFixed(2)+"%":"—",A=v.filing_type||"";return`<tr class="cp-inst-row ${A.includes("13D")?"cp-inst-13d":"cp-inst-13g"}">
      <td class="cp-inst-filer">${C}${p(v.filer_name||"Unknown")}</td>
      <td class="cp-inst-pct">${S}</td>
      <td class="cp-inst-filing-date">${p(d)}</td>
      <td class="cp-inst-filing-type">${p(A)}</td>
    </tr>`}).join(""),x=i.length>0?`
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
        <tbody>${I}</tbody>
      </table>
    </div>`:"",y='<div class="cp-inst-source">Source: SEC EDGAR (13F quarterly + 13D/13G real-time filings)</div>';t.innerHTML=o+c+m+g+x+y;const k=document.getElementById("cp-inst-tooltip-dismiss");k&&k.addEventListener("click",()=>{localStorage.setItem(pe,"1");const v=document.getElementById("cp-inst-tooltip");v&&v.remove()})}async function pt(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileInsiders){fe(s.companyProfileInsiders);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading insider transactions…</span>
  </div>`;try{const n=await w.fetch(`${T}/market/${encodeURIComponent(e)}/insiders`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileInsiders=i,s.companyProfileActiveTab==="insiders"&&fe(i)}catch(n){logger.warn("Error fetching insiders for",e,n),s.companyProfileActiveTab==="insiders"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load insider trading data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function fe(e){const t=l("#company-profile-body");if(!t)return;const n=e.insider_transactions||[];if(n.length===0){t.innerHTML=`<div class="cp-error">
      <div class="cp-error-icon">—</div>
      <p>No insider transaction data available for <strong>${p(e.symbol||"")}</strong></p>
    </div>`;return}const i=Date.now()-2160*60*60*1e3;let a=0,o=0,r=0,c=0;for(const y of n){if((y.filing_date?new Date(y.filing_date).getTime():0)<i)continue;const v=(y.transaction_type||"").toLowerCase(),d=Math.abs(y.total_value||0);v==="purchase"?(a+=d,r++):v==="sale"&&(o+=d,c++)}const u=a-o,f=u>0?"cp-insider-sentiment-buy":u<0?"cp-insider-sentiment-sell":"cp-insider-sentiment-neutral",m=u>0?"Net Buying":u<0?"Net Selling":"Neutral",h=u>0?"▲":u<0?"▼":"●",g=`<div class="cp-insider-sentiment ${f}">
    <div class="cp-insider-sentiment-header">
      <span class="cp-insider-sentiment-icon">${h}</span>
      <span class="cp-insider-sentiment-label">${m}</span>
      <span class="cp-insider-sentiment-period">90-day insider activity</span>
    </div>
    <div class="cp-insider-sentiment-stats">
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-buy-text">${r} buys</span>
        <span class="cp-insider-stat-amount">$${M(a)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-sell-text">${c} sells</span>
        <span class="cp-insider-stat-amount">$${M(o)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value">Net</span>
        <span class="cp-insider-stat-amount ${f}">${u>=0?"+":""}$${M(Math.abs(u))}</span>
      </div>
    </div>
  </div>`,I=`<div class="cp-insider-table-wrap">
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
      <tbody>${[...n].sort((y,k)=>{const v=y.filing_date||"";return(k.filing_date||"").localeCompare(v)}).map(y=>{const k=(y.transaction_type||"").toLowerCase();let v="cp-insider-row-other";k==="purchase"?v="cp-insider-row-buy":k==="sale"?v="cp-insider-row-sell":k==="option exercise"&&(v="cp-insider-row-exercise");const d=y.shares!=null?M(y.shares):"—",b=y.price_per_share!=null?"$"+y.price_per_share.toFixed(2):"—",C=y.total_value!=null?"$"+M(y.total_value):"—",S=y.shares_held_after!=null?M(y.shares_held_after):"—";return`<tr class="cp-insider-row ${v}">
      <td class="cp-insider-date">${p(y.filing_date||"")}</td>
      <td class="cp-insider-name">${p(y.insider_name||"Unknown")}</td>
      <td class="cp-insider-title">${p(y.title||"")}</td>
      <td class="cp-insider-type">${p(y.transaction_type||"")}</td>
      <td class="cp-insider-shares">${d}</td>
      <td class="cp-insider-price">${b}</td>
      <td class="cp-insider-total">${C}</td>
      <td class="cp-insider-holdings">${S}</td>
    </tr>`}).join("")}</tbody>
    </table>
  </div>`,x='<div class="cp-insider-source">Source: SEC EDGAR Form 4 (filed within 2 business days of transaction)</div>';t.innerHTML=g+I+x}function ut(){if(typeof w>"u")return;w.init();const e=l("#btn-signin");e&&e.addEventListener("click",()=>{w.showAuthModal("signin")});const t=l("#btn-signout");t&&t.addEventListener("click",()=>{w.signOut()});const n=l("#btn-user"),i=l("#user-dropdown");n&&i&&(n.addEventListener("click",a=>{a.stopPropagation(),i.classList.toggle("open")}),document.addEventListener("click",()=>{i.classList.remove("open")})),w.onAuthChange(a=>{ft(a)})}function ft(e){const t=l("#btn-signin"),n=l("#user-menu");if(e){t&&(t.style.display="none"),n&&(n.style.display="flex");const i=l("#user-avatar"),a=l("#user-name"),o=l("#dropdown-email");i&&e.photoURL&&(i.src=e.photoURL,i.alt=e.displayName||""),a&&(a.textContent=e.displayName||e.email||""),o&&(o.textContent=e.email||""),mt()}else t&&(t.style.display="flex"),n&&(n.style.display="none"),Le()}async function mt(){try{const e=await w.fetch(`${T}/auth/tier`);if(!e.ok)return;const t=await e.json(),n=t.tier||"free",i=n==="plus"?"pro":n,a=t.features||{};s.userTier=i,s.userFeatures=a,q(),P(),await F(),X(),Oe();const o=l("#tier-badge"),r=l("#dropdown-tier");if(o&&(o.textContent=i.toUpperCase(),o.className="tier-badge"+(i!=="free"?" "+i:"")),r){const c={free:"Free Plan",pro:"Pro Plan",plus:"Pro Plan"};r.textContent=c[i]||"Free Plan"}a.terminal_access===!1||i==="free"?Le():(vt(),Ve())}catch{}}function Le(){if(l("#upgrade-gate"))return;const e=document.createElement("div");e.id="upgrade-gate",e.style.cssText="position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(1,4,9,0.95);",e.innerHTML='<div style="text-align:center;max-width:420px;padding:40px;border:1px solid rgba(48,54,61,0.8);border-radius:12px;background:#0d1117;"><h2 style="color:#e6edf3;margin:0 0 12px;font-size:22px;">Upgrade to Pro</h2><p style="color:#8b949e;margin:0 0 24px;line-height:1.6;">The SIGNAL terminal requires a Pro subscription. Get full access to real-time news, sentiment analysis, and deduplication.</p><a href="/pricing" style="display:inline-block;padding:10px 28px;background:#238636;color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">View Plans</a><div style="margin-top:16px;"><a href="/" style="color:#8b949e;font-size:13px;text-decoration:underline;">Back to home</a></div></div>',document.body.appendChild(e),Ee(),ye()}function vt(){const e=l("#upgrade-gate");e&&e.remove()}function gt(){if(l("#max-upgrade-prompt"))return;const e=document.createElement("div");e.id="max-upgrade-prompt",e.className="modal-overlay open",e.innerHTML='<div class="modal" style="width:min(420px,90vw);text-align:center;padding:32px;"><div style="font-size:28px;margin-bottom:12px;">🚀</div><h2 style="color:var(--text-primary);margin:0 0 12px;font-size:18px;">Upgrade to Max</h2><p style="color:var(--text-secondary);margin:0 0 8px;line-height:1.5;font-size:13px;">AI-powered ticker recommendations, confidence scores, risk levels, and real-time market data are exclusive to the <strong>Max</strong> plan.</p><p style="color:var(--text-muted);margin:0 0 24px;font-size:12px;">Unlock the full trading terminal experience.</p><a href="/pricing" style="display:inline-block;padding:10px 28px;background:var(--blue);color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">View Max Plan</a><div style="margin-top:12px;"><button id="max-upgrade-dismiss" style="background:none;border:none;color:var(--text-muted);font-size:13px;cursor:pointer;padding:8px;">Maybe later</button></div></div>',e.addEventListener("click",t=>{(t.target===e||t.target.id==="max-upgrade-dismiss")&&e.remove()}),document.body.appendChild(e)}function me(){De(),Ue(),qe(),P(),Ke(),Ce(),st(),oe(),ut(),setInterval(oe,1e3),F(),V(),te(),Te(),setInterval(()=>{V(),te()},3e4)}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",me):me();document.addEventListener("DOMContentLoaded",function(){var e=document.getElementById("auth-gate"),t=document.getElementById("auth-gate-signin");function n(){typeof SignalAuth<"u"&&SignalAuth.isSignedIn()?e.classList.add("hidden"):e.classList.remove("hidden")}t&&t.addEventListener("click",function(){typeof SignalAuth<"u"&&SignalAuth.showAuthModal("signin")}),typeof SignalAuth<"u"&&SignalAuth.onAuthChange(n),setTimeout(function(){typeof SignalAuth<"u"&&(SignalAuth.onAuthChange(n),n())},500)});

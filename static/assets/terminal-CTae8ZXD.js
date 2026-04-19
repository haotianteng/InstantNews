import{S as k}from"./auth-C4Y_TkCR.js";/* empty css             *//* empty css                 */const S="/api",j=200,Be=6e4,ze=1e4,ce=10,P=[{id:"time",label:"Time",defaultVisible:!0,required:!1,requiredFeature:null},{id:"sentiment",label:"Sentiment",defaultVisible:!0,required:!1,requiredFeature:"sentiment_filter"},{id:"source",label:"Source",defaultVisible:!0,required:!1,requiredFeature:null},{id:"headline",label:"Headline",defaultVisible:!0,required:!0,requiredFeature:null},{id:"summary",label:"Summary",defaultVisible:!0,required:!1,requiredFeature:null},{id:"ticker",label:"Ticker",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"confidence",label:"Confidence",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"risk",label:"Risk Level",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"}],ee="instnews_column_visibility",te="instnews_column_order",ne="instnews_column_widths",Se="instnews_onboarding_done",W=60,xe={news:{name:"News Focus",icon:"📰",description:"Headlines, sources, and summaries at a glance.",visibility:{time:!0,sentiment:!1,source:!0,headline:!0,summary:!0,ticker:!1,confidence:!1,risk:!1},order:["time","source","headline","summary","sentiment","ticker","confidence","risk"]},trading:{name:"Trading View",icon:"📈",description:"Sentiment, tickers, and risk signals for active traders.",visibility:{time:!0,sentiment:!0,source:!1,headline:!0,summary:!1,ticker:!0,confidence:!0,risk:!0},order:["time","sentiment","ticker","headline","confidence","risk","source","summary"]},full:{name:"Full Terminal",icon:"🖥️",description:"Every column enabled — maximum information density.",visibility:{time:!0,sentiment:!0,source:!0,headline:!0,summary:!0,ticker:!0,confidence:!0,risk:!0},order:["time","sentiment","source","headline","summary","ticker","confidence","risk"]}},le={STOCK:{file:"stock.svg",fallback:"△",label:"Stock"},ETF:{file:"etf.svg",fallback:"◇",label:"ETF"},FUTURE:{file:"future.svg",fallback:"◎",label:"Futures"},CURRENCY:{file:"currency.svg",fallback:"¤",label:"Currency"},CRYPTO:{file:"crypto.svg",fallback:"₿",label:"Crypto"},BOND:{file:"bond.svg",fallback:"▬",label:"Bond"},OPTION:{file:"option.svg",fallback:"⊕",label:"Option"},"":{file:"stock.svg",fallback:"△",label:"Equity"}},Ve={CL:{name:"Crude Oil (WTI)",exchange:"NYMEX",unit:"1,000 barrels",tickSize:"$0.01",hours:"Sun–Fri 6:00pm–5:00pm ET"},NG:{name:"Natural Gas",exchange:"NYMEX",unit:"10,000 MMBtu",tickSize:"$0.001",hours:"Sun–Fri 6:00pm–5:00pm ET"},GC:{name:"Gold",exchange:"COMEX",unit:"100 troy oz",tickSize:"$0.10",hours:"Sun–Fri 6:00pm–5:00pm ET"},SI:{name:"Silver",exchange:"COMEX",unit:"5,000 troy oz",tickSize:"$0.005",hours:"Sun–Fri 6:00pm–5:00pm ET"},ES:{name:"E-mini S&P 500",exchange:"CME",unit:"$50 × index",tickSize:"$0.25",hours:"Sun–Fri 6:00pm–5:00pm ET"},NQ:{name:"E-mini Nasdaq 100",exchange:"CME",unit:"$20 × index",tickSize:"$0.25",hours:"Sun–Fri 6:00pm–5:00pm ET"},YM:{name:"E-mini Dow",exchange:"CBOT",unit:"$5 × index",tickSize:"$1.00",hours:"Sun–Fri 6:00pm–5:00pm ET"},ZB:{name:"30-Year T-Bond",exchange:"CBOT",unit:"$100,000 face",tickSize:"1/32 point",hours:"Sun–Fri 7:20pm–6:00pm ET"},ZC:{name:"Corn",exchange:"CBOT",unit:"5,000 bushels",tickSize:"$0.25/bu",hours:"Sun–Fri 7:00pm–7:45am, 8:30am–1:20pm CT"},ZW:{name:"Wheat",exchange:"CBOT",unit:"5,000 bushels",tickSize:"$0.25/bu",hours:"Sun–Fri 7:00pm–7:45am, 8:30am–1:20pm CT"},HG:{name:"Copper",exchange:"COMEX",unit:"25,000 lbs",tickSize:"$0.0005/lb",hours:"Sun–Fri 6:00pm–5:00pm ET"}};let n={items:[],seenIds:new Set,newIds:new Set,sources:[],stats:null,filter:{sentiment:"all",sourceType:"all",sources:new Set,query:"",dateFrom:"",dateTo:"",hideDuplicates:!1,tradableOnly:!1},nextBefore:null,loadingMore:!1,noMoreHistory:!1,rangeActive:!1,refreshInterval:5e3,refreshTimer:null,lastRefresh:null,connected:!1,loading:!0,totalFetched:0,fetchCount:0,itemsPerSecond:0,startTime:Date.now(),sidebarOpen:!1,modalOpen:!1,detailModalOpen:!1,detailItem:null,userTier:null,userFeatures:{},soundEnabled:!1,columnVisibility:{},columnOrder:P.map(e=>e.id),columnWidths:{},columnSettingsOpen:!1,marketPrices:{},priceRefreshTimer:null,companyProfileOpen:!1,companyProfileSymbol:null,companyProfileData:null,companyProfileLoading:!1,companyProfileActiveTab:"fundamentals",companyProfileFinancials:null,companyProfileCompetitors:null,companyProfileInstitutions:null,companyProfileInsiders:null};const l=e=>document.querySelector(e),M=e=>[...document.querySelectorAll(e)];function se(e){if(!e)return"--:--:--";try{const t=new Date(e);if(isNaN(t.getTime()))return"--:--:--";const s=new Date;if(t.getFullYear()===s.getFullYear()&&t.getMonth()===s.getMonth()&&t.getDate()===s.getDate())return t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"});const a=t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit"});if(t.getFullYear()===s.getFullYear())return`${t.toLocaleDateString("en-US",{month:"short",day:"2-digit"})} · ${a}`;const c=t.getFullYear(),r=String(t.getMonth()+1).padStart(2,"0"),o=String(t.getDate()).padStart(2,"0");return`${c}-${r}-${o} · ${a}`}catch{return"--:--:--"}}function Le(e){if(!e)return"";try{const t=new Date(e),i=new Date-t;return i<0?"just now":i<6e4?`${Math.floor(i/1e3)}s ago`:i<36e5?`${Math.floor(i/6e4)}m ago`:i<864e5?`${Math.floor(i/36e5)}h ago`:`${Math.floor(i/864e5)}d ago`}catch{return""}}function je(e){if(!e)return!1;try{const t=new Date(e);return Date.now()-t.getTime()<Be}catch{return!1}}function p(e){const t=document.createElement("div");return t.textContent=e,t.innerHTML}function We(e,t){return e?e.length>t?e.slice(0,t)+"…":e:""}function Ye(e){return e==null?"—":e>=1e12?"$"+(e/1e12).toFixed(2)+"T":e>=1e9?"$"+(e/1e9).toFixed(2)+"B":e>=1e6?"$"+(e/1e6).toFixed(2)+"M":"$"+e.toLocaleString()}async function F(){const e=document.getElementById("btn-refresh");e&&e.classList.add("refreshing");try{const s=!!(n.filter.dateFrom||n.filter.dateTo)?Math.max(j*5,1e3):j,i=new URLSearchParams({limit:s});n.filter.dateFrom&&i.set("from",n.filter.dateFrom),n.filter.dateTo&&i.set("to",n.filter.dateTo),n.filter.sourceType&&n.filter.sourceType!=="all"&&i.set("source_type",n.filter.sourceType);const a=await k.fetch(`${S}/news?${i}`);if(!a.ok)throw new Error(`HTTP ${a.status}`);const c=await a.json();if(n.connected=!0,n.loading=!1,n.fetchCount++,n.lastRefresh=new Date().toISOString(),c.items&&c.items.length>0){const r=new Set;for(const d of c.items)n.seenIds.has(d.id)||(r.add(d.id),n.seenIds.add(d.id));n.soundEnabled&&r.size>0&&n.fetchCount>1&&Ke(),n.newIds=r,n.items=c.items,n.totalFetched=c.count,n.nextBefore=c.next_before||null,n.noMoreHistory=!c.next_before||c.items.length<s;const o=(Date.now()-n.startTime)/1e3;n.itemsPerSecond=o>0?(n.totalFetched/o).toFixed(1):0}T(),wt(),ve(!0),ie()}catch{n.connected=!1,n.loading=!1,ve(!1),n.items.length===0&&ut("Unable to connect to API. Retrying...")}finally{e&&e.classList.remove("refreshing")}}async function Ge(){if(!(n.loadingMore||n.noMoreHistory||!n.nextBefore)){n.loadingMore=!0;try{const e=new URLSearchParams({limit:j,before:n.nextBefore});n.filter.dateFrom&&e.set("from",n.filter.dateFrom),n.filter.dateTo&&e.set("to",n.filter.dateTo),n.filter.sourceType&&n.filter.sourceType!=="all"&&e.set("source_type",n.filter.sourceType);const t=await k.fetch(`${S}/news?${e}`);if(!t.ok)throw new Error(`HTTP ${t.status}`);const s=await t.json();if(s.items&&s.items.length>0){for(const i of s.items)n.seenIds.has(i.id)||(n.seenIds.add(i.id),n.items.push(i));n.nextBefore=s.next_before||null,n.noMoreHistory=!s.next_before||s.items.length<j,T()}else n.noMoreHistory=!0,T()}catch{}finally{n.loadingMore=!1}}}async function de(){try{const e=await k.fetch(`${S}/sources`);if(!e.ok)return;const t=await e.json();n.sources=t.sources||[],He()}catch{}}async function Q(){try{const e=await k.fetch(`${S}/stats`);if(!e.ok)return;n.stats=await e.json(),bt()}catch{}}async function ie(){if(!n.userFeatures.ai_ticker_recommendations||!n.columnVisibility.ticker)return;const e={};n.items.forEach(s=>{s.target_asset&&!e[s.target_asset]&&(e[s.target_asset]=s.asset_type||"")});const t=Object.keys(e);if(t.length!==0){for(let s=0;s<t.length;s+=ce){const a=t.slice(s,s+ce).map(async c=>{try{const r=e[c],o=r?`?asset_type=${encodeURIComponent(r)}`:"",d=await k.fetch(`${S}/market/${encodeURIComponent(c)}${o}`);d.ok&&(n.marketPrices[c]=await d.json())}catch{}});await Promise.all(a)}T()}}function Xe(){_e(),n.userFeatures.ai_ticker_recommendations&&n.columnVisibility.ticker&&(n.priceRefreshTimer=setInterval(ie,ze))}function _e(){n.priceRefreshTimer&&(clearInterval(n.priceRefreshTimer),n.priceRefreshTimer=null)}async function ue(){try{const e=l("#btn-refresh");e&&(e.disabled=!0,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>Refreshing'),await k.fetch(`${S}/refresh`,{method:"POST"}),await F(),await Q(),e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}catch{const e=l("#btn-refresh");e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}}function Ke(){try{const e=new(window.AudioContext||window.webkitAudioContext),t=e.createOscillator(),s=e.createGain();t.connect(s),s.connect(e.destination),t.type="sine",t.frequency.setValueAtTime(880,e.currentTime),t.frequency.setValueAtTime(1100,e.currentTime+.05),s.gain.setValueAtTime(.08,e.currentTime),s.gain.exponentialRampToValueAtTime(.001,e.currentTime+.15),t.start(e.currentTime),t.stop(e.currentTime+.15)}catch{}}function Me(){return n.items.filter(e=>{if(n.filter.sentiment!=="all"&&e.sentiment_label!==n.filter.sentiment||n.filter.sources.size>0&&!n.filter.sources.has(e.source))return!1;if(n.filter.query){const t=n.filter.query.toLowerCase(),s=(e.title||"").toLowerCase().includes(t),i=(e.summary||"").toLowerCase().includes(t);if(!s&&!i)return!1}return!(n.filter.hideDuplicates&&e.duplicate||n.filter.tradableOnly&&e.tradeable!==!0)})}function Je(){const e={all:0,bullish:0,bearish:0,neutral:0};for(const t of n.items)e.all++,e[t.sentiment_label]!==void 0&&e[t.sentiment_label]++;return e}function Qe(){try{const t=localStorage.getItem(ee);if(t){const s=JSON.parse(t),i={};for(const a of P)i[a.id]=a.id in s?s[a.id]:a.defaultVisible;n.columnVisibility=i;return}}catch{}const e={};for(const t of P)e[t.id]=t.defaultVisible;n.columnVisibility=e}function Ie(){try{localStorage.setItem(ee,JSON.stringify(n.columnVisibility))}catch{}}function Ze(){try{const e=localStorage.getItem(te);if(e){const t=JSON.parse(e);if(Array.isArray(t)){const s=new Set(P.map(a=>a.id)),i=t.filter(a=>s.has(a));for(const a of P)i.includes(a.id)||i.push(a.id);n.columnOrder=i;return}}}catch{}n.columnOrder=P.map(e=>e.id)}function ae(){try{localStorage.setItem(te,JSON.stringify(n.columnOrder))}catch{}}function et(){try{const e=localStorage.getItem(ne);if(e){const t=JSON.parse(e);if(t&&typeof t=="object"){const s={};for(const i of P)i.id in t&&typeof t[i.id]=="number"&&t[i.id]>=W&&(s[i.id]=t[i.id]);n.columnWidths=s;return}}}catch{}n.columnWidths={}}function re(){try{localStorage.setItem(ne,JSON.stringify(n.columnWidths))}catch{}}function Fe(){const e={};for(const t of P)e[t.id]=t;return n.columnOrder.map(t=>e[t]).filter(Boolean)}function Pe(e){return!e.requiredFeature||n.userTier===null?!1:!n.userFeatures[e.requiredFeature]}function q(){return Fe().filter(e=>Pe(e)?!1:n.columnVisibility[e.id]!==!1)}function tt(){return localStorage.getItem(ee)!==null||localStorage.getItem(te)!==null||localStorage.getItem(ne)!==null}function nt(){return!(n.userTier!=="max"||localStorage.getItem(Se)||tt())}function pe(e){const t=xe[e];t&&(n.columnVisibility={...t.visibility},n.columnOrder=[...t.order],n.columnWidths={},Ie(),ae(),re(),H(),Y(),T())}function fe(){try{localStorage.setItem(Se,"1")}catch{}const e=l("#onboarding-overlay");e&&e.remove()}function st(){if(!nt())return;const e=document.createElement("div");e.id="onboarding-overlay",e.className="onboarding-overlay";const t=Object.entries(xe).map(([i,a])=>{const c=P.filter(r=>a.visibility[r.id]).map(r=>`<span>${r.label}</span>`).join("");return`<div class="onboarding-preset" data-preset="${i}">
      <div class="onboarding-preset-icon">${a.icon}</div>
      <div class="onboarding-preset-name">${a.name}</div>
      <div class="onboarding-preset-desc">${a.description}</div>
      <div class="onboarding-preset-cols">${c}</div>
    </div>`}).join("");e.innerHTML=`<div class="onboarding-card">
    <h2>Choose Your Layout</h2>
    <p>Pick a starting layout for your terminal. You can always customize columns later.</p>
    <div class="onboarding-presets">${t}</div>
    <button class="onboarding-skip" id="onboarding-skip">Customize later</button>
  </div>`,document.body.appendChild(e),e.querySelectorAll(".onboarding-preset").forEach(i=>{i.addEventListener("click",()=>{const a=i.getAttribute("data-preset");pe(a),fe()})});const s=e.querySelector("#onboarding-skip");s&&s.addEventListener("click",()=>{pe("full"),fe()})}function H(){const e=document.querySelector(".news-table thead");if(!e)return;const t=q();e.innerHTML="<tr>"+t.map(i=>{const a=n.columnWidths[i.id],c=a?` style="width:${a}px"`:"";return`<th class="col-${i.id}" draggable="true" data-col-id="${i.id}"${c}><span class="th-drag-label">${i.label}</span><span class="col-resize-handle" data-col-id="${i.id}"></span></th>`}).join("")+"</tr>";const s=document.querySelector(".news-table");s&&(s.style.tableLayout=Object.keys(n.columnWidths).length>0?"fixed":""),at(),it()}function it(){const e=document.querySelector(".news-table thead tr");if(!e)return;const t=e.querySelectorAll("th[draggable]");let s=null;t.forEach(i=>{i.addEventListener("dragstart",a=>{if(a.target.closest(".col-resize-handle")){a.preventDefault();return}s=i,i.classList.add("th-dragging"),a.dataTransfer.effectAllowed="move",a.dataTransfer.setData("text/plain",i.dataset.colId)}),i.addEventListener("dragover",a=>{if(a.preventDefault(),a.dataTransfer.dropEffect="move",!s||i===s)return;e.querySelectorAll("th").forEach(o=>o.classList.remove("th-drag-over-left","th-drag-over-right"));const c=i.getBoundingClientRect(),r=c.left+c.width/2;a.clientX<r?i.classList.add("th-drag-over-left"):i.classList.add("th-drag-over-right")}),i.addEventListener("dragleave",()=>{i.classList.remove("th-drag-over-left","th-drag-over-right")}),i.addEventListener("drop",a=>{if(a.preventDefault(),a.stopPropagation(),!s||i===s)return;e.querySelectorAll("th").forEach(w=>w.classList.remove("th-drag-over-left","th-drag-over-right"));const c=s.dataset.colId,r=i.dataset.colId,o=[...n.columnOrder],d=o.indexOf(c),f=o.indexOf(r);if(d===-1||f===-1)return;o.splice(d,1);const g=i.getBoundingClientRect(),h=g.left+g.width/2,m=a.clientX<h?o.indexOf(r):o.indexOf(r)+1;o.splice(m,0,c),n.columnOrder=o,ae(),H(),T(),n.columnSettingsOpen&&Y()}),i.addEventListener("dragend",()=>{i.classList.remove("th-dragging"),e.querySelectorAll("th").forEach(a=>a.classList.remove("th-drag-over-left","th-drag-over-right"))})})}function at(){document.querySelectorAll(".col-resize-handle").forEach(t=>{t.addEventListener("mousedown",rt),t.addEventListener("dblclick",ot)})}function rt(e){e.preventDefault(),e.stopPropagation();const t=e.target,s=t.parentElement,i=t.dataset.colId,a=e.clientX,c=s.offsetWidth,r=document.querySelector(".news-table");r&&(r.style.tableLayout="fixed");const o=[...document.querySelectorAll(".news-table thead th")];let d=0;o.forEach(h=>{const m=h.offsetWidth;h.style.width=m+"px",d+=m}),r&&(r.style.width=d+"px"),document.body.style.cursor="col-resize",document.body.style.userSelect="none",t.classList.add("active");function f(h){const m=h.clientX-a,w=Math.max(W,c+m);s.style.width=w+"px",r&&(r.style.width=d+(w-c)+"px")}function g(h){document.removeEventListener("mousemove",f),document.removeEventListener("mouseup",g),document.body.style.cursor="",document.body.style.userSelect="",t.classList.remove("active"),o.forEach(w=>{const L=w.dataset.colId;L&&(n.columnWidths[L]=w.offsetWidth)});const m=h.clientX-a;n.columnWidths[i]=Math.max(W,c+m),r&&(r.style.width=""),re(),H(),T()}document.addEventListener("mousemove",f),document.addEventListener("mouseup",g)}function ot(e){e.preventDefault(),e.stopPropagation();const t=e.target.dataset.colId,i=q().findIndex(f=>f.id===t);if(i===-1)return;const a=document.querySelectorAll("#news-body tr");let c=W;const r=e.target.parentElement,o=document.createElement("span");o.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;",o.textContent=r.textContent,document.body.appendChild(o),c=Math.max(c,o.offsetWidth+32),document.body.removeChild(o),a.forEach(f=>{if(f.classList.contains("skeleton-row"))return;const h=f.querySelectorAll("td")[i];if(!h)return;const m=document.createElement("div");m.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:12px;",m.innerHTML=h.innerHTML,document.body.appendChild(m),c=Math.max(c,m.offsetWidth+24),document.body.removeChild(m)}),c=Math.min(c,600);const d=document.querySelector(".news-table");d&&(d.style.tableLayout="fixed"),n.columnWidths[t]=c,re(),H(),T()}function ct(e,t,s,i){switch(e){case"time":return`<td class="cell-time" title="${Le(t.published)}">${se(t.published)}</td>`;case"sentiment":return`<td class="cell-sentiment"><span class="sentiment-badge ${t.sentiment_label}"><span class="sentiment-dot"></span>${t.sentiment_label}</span></td>`;case"source":return`<td class="cell-source"><span class="source-tag">${p(t.source||"")}</span></td>`;case"headline":{const a=t.tradeable?'<span class="t-bolt"><img src="./assets/lightneingClearBG.png" alt="Tradeable"></span>':"";return`<td class="cell-headline"><a href="${p(t.link||"#")}" target="_blank" rel="noopener noreferrer">${p(t.title||"Untitled")}</a>${s?'<span class="badge-new">NEW</span>':""}${a}${i}</td>`}case"summary":return`<td class="cell-summary">${p(We(t.summary,120))}</td>`;case"ticker":{if(!t.target_asset)return'<td class="cell-ticker"><span class="cell-dash">—</span></td>';const a=p(t.target_asset),c=(t.asset_type||"").toUpperCase(),r=le[c]||le[""],o=n.marketPrices[t.target_asset];let d="";if(o&&o.price!=null&&o.price>0){const f=o.change_percent||0,g=f>=0?"+":"",h=f>0?"price-up":f<0?"price-down":"price-flat",m=o.market_status,w=m==="closed"?'<span class="market-label-closed">Closed</span>':m==="24h"?'<span class="market-label-24h">24H</span>':"";d=`<span class="ticker-price ${h}">$${o.price.toFixed(2)} <span class="ticker-change">${g}${f.toFixed(2)}%</span>${w}</span>`}return`<td class="cell-ticker"><span class="ticker-badge" data-ticker="${a}" data-asset-type="${p(c)}"><span class="asset-icon" title="${p(r.label)}"><img src="./assets/icons/${r.file}" alt="${p(r.label)}" onerror="this.parentElement.textContent='${r.fallback}'"></span>${a}${d}</span></td>`}case"confidence":return`<td class="cell-confidence">${t.confidence!=null?Math.round(t.confidence*100)+"%":'<span class="cell-dash">—</span>'}</td>`;case"risk":{if(!t.risk_level)return'<td class="cell-risk"><span class="cell-dash">—</span></td>';const a=t.risk_level.toLowerCase();return`<td class="cell-risk"><span class="risk-badge ${a==="low"?"green":a==="high"?"red":"yellow"}">${p(t.risk_level.toUpperCase())}</span></td>`}default:return"<td></td>"}}function me(e){const t=typeof e=="boolean"?e:!n.columnSettingsOpen;n.columnSettingsOpen=t;const s=l("#column-settings-panel");s&&s.classList.toggle("open",t)}function Y(){const e=l("#column-settings-panel");if(!e)return;const s=Fe().map(r=>{const o=Pe(r),d=!o&&n.columnVisibility[r.id]!==!1,f=r.required||o;return`<div class="col-toggle-item${o?" locked":""}${r.required?" required":""}" draggable="true" data-col-id="${r.id}">
      <span class="col-drag-handle" aria-label="Drag to reorder">≡</span>
      <span class="col-toggle-label">
        ${o?'<svg class="col-lock-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg><span class="col-max-badge">MAX</span>':""}
        ${p(r.label)}
      </span>
      <label class="col-toggle-switch${f?" disabled":""}">
        <input type="checkbox" ${d?"checked":""} ${f?"disabled":""} data-col-id="${r.id}">
        <span class="col-toggle-track"><span class="col-toggle-thumb"></span></span>
      </label>
    </div>`});e.innerHTML=`<div class="col-settings-header"><span>Columns</span></div>
    <div class="col-settings-list">${s.join("")}</div>`,e.querySelectorAll('input[type="checkbox"]').forEach(r=>{r.addEventListener("change",o=>{const d=o.target.dataset.colId;n.columnVisibility[d]=o.target.checked,Ie(),H(),T()})}),e.querySelectorAll(".col-toggle-item.locked").forEach(r=>{r.style.cursor="pointer",r.addEventListener("click",o=>{o.target.closest("input")||At()})});const i=e.querySelector(".col-settings-list");let a=null,c=!1;i.querySelectorAll(".col-drag-handle").forEach(r=>{r.addEventListener("mousedown",()=>{c=!0})}),document.addEventListener("mouseup",()=>{c=!1},{once:!1}),i.querySelectorAll(".col-toggle-item[draggable]").forEach(r=>{r.addEventListener("dragstart",o=>{if(!c){o.preventDefault();return}a=r,n._dragging=!0,r.classList.add("dragging"),o.dataTransfer.effectAllowed="move",o.dataTransfer.setData("text/plain",r.dataset.colId)}),r.addEventListener("dragover",o=>{if(o.preventDefault(),o.dataTransfer.dropEffect="move",!a||r===a)return;i.querySelectorAll(".col-toggle-item").forEach(g=>g.classList.remove("drag-over-above","drag-over-below"));const d=r.getBoundingClientRect(),f=d.top+d.height/2;o.clientY<f?r.classList.add("drag-over-above"):r.classList.add("drag-over-below")}),r.addEventListener("dragleave",()=>{r.classList.remove("drag-over-above","drag-over-below")}),r.addEventListener("drop",o=>{if(o.preventDefault(),o.stopPropagation(),!a||r===a)return;i.querySelectorAll(".col-toggle-item").forEach(h=>h.classList.remove("drag-over-above","drag-over-below"));const d=r.getBoundingClientRect(),f=d.top+d.height/2;o.clientY<f?i.insertBefore(a,r):i.insertBefore(a,r.nextSibling);const g=[...i.querySelectorAll(".col-toggle-item[data-col-id]")].map(h=>h.dataset.colId);n.columnOrder=g,ae(),H(),T()}),r.addEventListener("dragend",()=>{r.classList.remove("dragging"),n._dragging=!1,i.querySelectorAll(".col-toggle-item").forEach(o=>o.classList.remove("drag-over-above","drag-over-below"))})}),i.addEventListener("dragover",r=>{r.preventDefault()})}function T(){const e=l("#news-body");if(!e)return;const t=Me(),s=q(),i=s.length;if(t.length===0&&!n.loading){e.innerHTML=`
      <tr>
        <td colspan="${i}">
          <div class="empty-state">
            <div class="icon">◇</div>
            <div>No items match current filters</div>
            <div style="font-size:11px">Try adjusting sentiment or source filters</div>
          </div>
        </td>
      </tr>`;return}const a=t.map(r=>{const o=n.newIds.has(r.id),d=je(r.fetched_at),f=o?"news-row-new":"",g=r.duplicate?'<span class="badge-dup">DUP</span>':"",h=s.map(m=>ct(m.id,r,d,g)).join("");return`<tr class="${f}" data-id="${r.id}">${h}</tr>`});let c="";if(n.noMoreHistory)c=`<tr class="load-more-row"><td colspan="${i}"><div class="load-more-sentinel">end of history</div></td></tr>`;else{const r=n.loadingMore?'<span class="spinner"></span> loading older…':"scroll for more";c=`<tr class="load-more-row"><td colspan="${i}"><div class="load-more-sentinel" id="load-more-sentinel">${r}</div></td></tr>`}e.innerHTML=a.join("")+c,lt(),vt(),yt()}let B=null;function lt(){const e=document.getElementById("load-more-sentinel");e&&(B?B.disconnect():B=new IntersectionObserver(t=>{for(const s of t)s.isIntersecting&&Ge()},{root:null,rootMargin:"400px",threshold:0}),B.observe(e))}function dt(){const e=l("#news-body");if(!e)return;const t=q(),s=Array.from({length:15},()=>`<tr class="skeleton-row">${t.map(a=>`<td><div class="skeleton-block" style="width:${a.id==="headline"?200+Math.random()*200:a.id==="summary"?100+Math.random()*100:50+Math.random()*30}px"></div></td>`).join("")}</tr>`);e.innerHTML=s.join("")}function ut(e){const t=l("#news-body");if(!t)return;const s=q().length;t.innerHTML=`
    <tr>
      <td colspan="${s}">
        <div class="loading-state">
          <div class="loading-spinner"></div>
          <div>${p(e)}</div>
        </div>
      </td>
    </tr>`}function pt(e){return e.startsWith("Twitter/@")?"twitter":e.startsWith("TruthSocial/@")?"truth":"rss"}const ft=[{id:"rss",label:"News (RSS)",defaultCollapsed:!1},{id:"twitter",label:"Twitter (Diplomatic)",defaultCollapsed:!0},{id:"truth",label:"Truth Social",defaultCollapsed:!0}];function Ae(e){return`signal_sources_collapsed_${e}`}function mt(e,t){const s=localStorage.getItem(Ae(e));return s==="1"?!0:s==="0"?!1:!!t}function gt(e,t){localStorage.setItem(Ae(e),t?"1":"0")}function ht(e){return e.startsWith("Twitter/")?e.slice(8):e.startsWith("TruthSocial/")?e.slice(12):e.replace(/_/g," ")}function He(){const e=l("#source-list");if(!e)return;let t=n.sources;t.length||(t=["CNBC","CNBC_World","Reuters_Business","MarketWatch","MarketWatch_Markets","Investing_com","Yahoo_Finance","Nasdaq","SeekingAlpha","Benzinga","AP_News","Bloomberg_Business","Bloomberg_Markets","BBC_Business","Google_News_Business"].map(d=>({name:d,total_items:null})));const s={rss:[],twitter:[],truth:[]};for(const o of t){const d=pt(o.name);s[d].push(o)}const i=`
    <div class="source-toolbar">
      <button type="button" class="source-toolbar-btn" id="src-select-all">All</button>
      <button type="button" class="source-toolbar-btn" id="src-select-none">None</button>
    </div>
  `,a=ft.map(o=>{const d=s[o.id]||[];if(!d.length)return"";const f=mt(o.id,o.defaultCollapsed),g=d.map(m=>`
      <label class="source-item source-item--child">
        <input type="checkbox" checked data-source="${p(m.name)}">
        <span>${p(ht(m.name))}</span>
        <span class="source-count">${m.total_items==null?"--":m.total_items}</span>
      </label>
    `).join(""),h=d.length;return`
      <div class="source-group" data-group="${o.id}" ${f?'data-collapsed="1"':""}>
        <label class="source-group-header">
          <input type="checkbox" class="source-group-parent" data-group-parent="${o.id}" checked>
          <button type="button" class="source-group-caret" aria-label="toggle">
            <span class="caret">${f?"▸":"▾"}</span>
          </button>
          <span class="source-group-label">${p(o.label)}</span>
          <span class="source-group-count">${h}</span>
        </label>
        <div class="source-group-children">${g}</div>
      </div>
    `}).join("");e.innerHTML=i+a,e.querySelectorAll('input[type="checkbox"][data-source]').forEach(o=>{o.addEventListener("change",()=>{he(),Z(),T()})}),e.querySelectorAll("input[data-group-parent]").forEach(o=>{o.addEventListener("change",d=>{const f=o.dataset.groupParent,g=o.checked;e.querySelectorAll(`.source-group[data-group="${f}"] input[type="checkbox"][data-source]`).forEach(h=>{h.checked=g}),o.indeterminate=!1,Z(),T()})}),e.querySelectorAll(".source-group-caret").forEach(o=>{o.addEventListener("click",d=>{d.preventDefault(),d.stopPropagation();const f=o.closest(".source-group");if(!f)return;const g=f.dataset.group,h=f.getAttribute("data-collapsed")!=="1";h?f.setAttribute("data-collapsed","1"):f.removeAttribute("data-collapsed");const m=o.querySelector(".caret");m&&(m.textContent=h?"▸":"▾"),gt(g,h)})});const c=e.querySelector("#src-select-all"),r=e.querySelector("#src-select-none");c&&c.addEventListener("click",()=>ge(!0)),r&&r.addEventListener("click",()=>ge(!1)),he()}function ge(e){M('#source-list input[type="checkbox"][data-source]').forEach(t=>{t.checked=e}),M("#source-list input[data-group-parent]").forEach(t=>{t.checked=e,t.indeterminate=!1}),Z(),T()}function he(){M(".source-group").forEach(e=>{e.dataset.group;const t=e.querySelector("input[data-group-parent]"),s=Array.from(e.querySelectorAll('input[type="checkbox"][data-source]'));if(!t||!s.length)return;const i=s.filter(a=>a.checked).length;i===0?(t.checked=!1,t.indeterminate=!1):i===s.length?(t.checked=!0,t.indeterminate=!1):(t.checked=!1,t.indeterminate=!0)})}function Z(){const e=new Set,t=[];M('#source-list input[type="checkbox"][data-source]').forEach(s=>{s.checked?t.push(s.dataset.source):e.add(s.dataset.source)}),e.size===0?n.filter.sources=new Set:n.filter.sources=new Set(t)}function vt(){const e=Je(),t={all:l("#sentiment-count-all"),bullish:l("#sentiment-count-bullish"),bearish:l("#sentiment-count-bearish"),neutral:l("#sentiment-count-neutral")};Object.entries(t).forEach(([s,i])=>{i&&(i.textContent=e[s]||0)})}function yt(){const e=l("#total-items");if(e){const t=Me();e.textContent=t.length}}function bt(){if(!n.stats)return;const e=l("#total-items");e&&n.filter.sentiment==="all"&&n.filter.sources.size===0&&!n.filter.query&&(e.textContent=n.stats.total_items);const t=l("#feed-count");t&&(t.textContent=n.stats.feed_count);const s=l("#avg-sentiment");if(s){const i=n.stats.avg_sentiment_score;s.textContent=(i>=0?"+":"")+i.toFixed(3),s.style.color=i>.05?"var(--green)":i<-.05?"var(--red)":"var(--yellow)"}}function ve(e){const t=l("#connection-dot"),s=l("#connection-label");t&&(t.className=e?"status-dot connected":"status-dot disconnected"),s&&(s.textContent=e?"LIVE":"DISCONNECTED")}function wt(){const e=l("#last-refresh");e&&n.lastRefresh&&(e.textContent=se(n.lastRefresh));const t=l("#items-per-sec");t&&(t.textContent=n.itemsPerSecond)}function ye(){const e=l("#clock");if(!e)return;const t=new Date,s=t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"}),i=t.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric",year:"numeric"});e.textContent=`${i}  ${s}`}function Re(){Oe(),n.refreshTimer=setInterval(()=>{F()},n.refreshInterval)}function Oe(){n.refreshTimer&&(clearInterval(n.refreshTimer),n.refreshTimer=null)}function $t(){M(".sentiment-filter-btn").forEach(u=>{u.addEventListener("click",()=>{const v=u.dataset.sentiment;n.filter.sentiment=v,M(".sentiment-filter-btn").forEach(x=>x.classList.remove("active")),u.classList.add("active"),T()})}),M(".source-type-filter-btn").forEach(u=>{u.addEventListener("click",()=>{const v=u.dataset.sourceType;n.filter.sourceType=v,M(".source-type-filter-btn").forEach(x=>x.classList.remove("active")),u.classList.add("active"),F()})});const e=l("#search-input");if(e){let u;e.addEventListener("input",v=>{clearTimeout(u),u=setTimeout(()=>{n.filter.query=v.target.value.trim(),T()},150)})}const t=l("#date-from"),s=l("#date-to"),i=l("#btn-apply-filters"),a=l("#apply-hint"),c=l("#btn-clear-dates");function r(){const u=(n.userTier||"free").toLowerCase();return u==="free"?7:u==="plus"?14:30}function o(){if(!t||!s)return{ok:!0};const u=t.value,v=s.value;if(!u&&!v)return{ok:!0};if(u&&v&&u>v)return{ok:!1,msg:"From date must be before To"};const x=r();return u&&v&&(new Date(v)-new Date(u))/(1e3*60*60*24)>x?{ok:!1,msg:`Range too wide (max ${x} days on your plan). Use the API for larger queries.`}:{ok:!0}}function d(u,v=!1){a&&(a.textContent=u||"",a.classList.toggle("apply-err",!!v))}function f(){const u=o();if(!u.ok){d(u.msg,!0);return}n.filter.dateFrom=t?t.value:"",n.filter.dateTo=s?s.value:"",n.filter.query=e?e.value.trim():n.filter.query;const v=!!(n.filter.dateFrom||n.filter.dateTo);n.rangeActive=v,n.refreshTimer&&(clearInterval(n.refreshTimer),n.refreshTimer=null),v||(n.refreshTimer=setInterval(()=>{F()},n.refreshInterval)),n.nextBefore=null,n.noMoreHistory=!1,d(v?`Range active — auto-refresh paused. Max ${r()} days.`:""),F()}i&&i.addEventListener("click",f),e&&e.addEventListener("keydown",u=>{u.key==="Enter"&&(u.preventDefault(),f())}),c&&c.addEventListener("click",()=>{n.filter.dateFrom="",n.filter.dateTo="",n.rangeActive=!1,t&&(t.value=""),s&&(s.value=""),d(""),n.refreshTimer&&clearInterval(n.refreshTimer),n.refreshTimer=setInterval(()=>{F()},n.refreshInterval),n.nextBefore=null,n.noMoreHistory=!1,F()});const g=l("#hide-duplicates");g&&g.addEventListener("change",u=>{n.filter.hideDuplicates=u.target.checked,T()});const h=l("#tradable-only");h&&h.addEventListener("change",u=>{n.filter.tradableOnly=u.target.checked,T()});const m=l("#btn-refresh");m&&m.addEventListener("click",ue);const w=l("#refresh-interval");w&&w.addEventListener("change",u=>{n.refreshInterval=parseInt(u.target.value,10),Re()});const L=l("#btn-docs");L&&L.addEventListener("click",()=>V(!0));const R=l("#modal-close");R&&R.addEventListener("click",()=>V(!1));const I=l("#modal-overlay");I&&I.addEventListener("click",u=>{u.target===I&&V(!1)});const b=l("#btn-col-settings");b&&b.addEventListener("click",u=>{u.stopPropagation(),me(),n.columnSettingsOpen&&Y()}),document.addEventListener("click",u=>{n._dragging||n.columnSettingsOpen&&!u.target.closest("#column-settings-wrap")&&me(!1)});const C=l("#news-body");C&&C.addEventListener("click",u=>{if(u.target.closest("a"))return;const v=u.target.closest(".ticker-badge[data-ticker]");if(v){u.stopPropagation(),De(v.dataset.ticker,v.dataset.assetType||"");return}const x=u.target.closest("tr[data-id]");if(!x)return;const oe=x.dataset.id,X=n.items.find(qe=>String(qe.id)===oe);X&&kt(X)});const y=l("#detail-modal-close");y&&y.addEventListener("click",J);const $=l("#detail-modal-overlay");$&&$.addEventListener("click",u=>{u.target===$&&J()});const O=document.getElementById("company-profile-close");O&&O.addEventListener("click",be);const _=document.querySelectorAll(".cp-tab");_.forEach(u=>{u.addEventListener("click",()=>{const v=u.dataset.tab;v!==n.companyProfileActiveTab&&(n.companyProfileActiveTab=v,_.forEach(x=>x.classList.toggle("active",x.dataset.tab===v)),v==="overview"||(v==="fundamentals"&&n.companyProfileData?Ne(n.companyProfileData):v==="financials"?St(n.companyProfileSymbol):v==="competitors"?xt(n.companyProfileSymbol):v==="institutions"?Lt(n.companyProfileSymbol):v==="insiders"&&_t(n.companyProfileSymbol)))})});const E=l("#btn-sound");E&&E.addEventListener("click",()=>{n.soundEnabled=!n.soundEnabled,E.classList.toggle("active",n.soundEnabled),E.title=n.soundEnabled?"Sound alerts ON":"Sound alerts OFF";const u=E.querySelector(".sound-icon");u&&(u.innerHTML=n.soundEnabled?'<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>':'<path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>')});const D=l("#hamburger-btn");D&&D.addEventListener("click",K);const G=l("#sidebar-backdrop");G&&G.addEventListener("click",()=>K(!1)),document.addEventListener("keydown",u=>{if(u.target.tagName==="INPUT"||u.target.tagName==="TEXTAREA"||u.target.tagName==="SELECT"){u.key==="Escape"&&u.target.blur();return}switch(u.key.toLowerCase()){case"r":u.preventDefault(),ue();break;case"f":u.preventDefault();const v=l("#search-input");v&&v.focus();break;case"1":u.preventDefault(),z("all");break;case"2":u.preventDefault(),z("bullish");break;case"3":u.preventDefault(),z("bearish");break;case"4":u.preventDefault(),z("neutral");break;case"escape":n.companyProfileOpen?be():n.detailModalOpen?J():n.modalOpen&&V(!1),n.sidebarOpen&&K(!1);break}});const N=l("#api-url");N&&N.addEventListener("click",()=>{const u=`${S}/news`;navigator.clipboard&&navigator.clipboard.writeText(u).then(()=>{N.textContent="Copied!",setTimeout(()=>{N.textContent=`${S}/news`},1500)})})}function z(e){n.filter.sentiment=e,M(".sentiment-filter-btn").forEach(t=>{t.classList.toggle("active",t.dataset.sentiment===e)}),T()}function K(e){const t=typeof e=="boolean"?e:!n.sidebarOpen;n.sidebarOpen=t;const s=l(".sidebar"),i=l("#sidebar-backdrop");s&&s.classList.toggle("open",t),i&&i.classList.toggle("open",t)}function V(e){n.modalOpen=e;const t=l("#modal-overlay");t&&t.classList.toggle("open",e),e&&M(".api-base-url").forEach(s=>{s.textContent=window.location.origin+window.location.pathname.replace(/\/[^/]*$/,"")})}function kt(e){n.detailItem=e,n.detailModalOpen=!0;const t=l("#detail-modal-overlay");if(!t)return;const s=n.userTier==="max";let i="";if(i+=`<div class="detail-article">
    <h3 class="detail-headline">${p(e.title||"Untitled")}</h3>
    <div class="detail-meta">
      <span class="source-tag">${p(e.source||"")}</span>
      <span class="detail-time">${se(e.published)} · ${Le(e.published)}</span>
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
    </div>`;else{const c=e.confidence!=null?Math.round(e.confidence*100):"—",r=(e.risk_level||"").toLowerCase(),o=r==="low"?"green":r==="high"?"red":"yellow",d=e.tradeable?"YES":"NO",f=e.tradeable?"yes":"no",g=(e.sentiment_label||"neutral").toLowerCase(),h=e.sentiment_score!=null?(e.sentiment_score>=0?"+":"")+Number(e.sentiment_score).toFixed(2):"—";i+=`<div class="detail-ticker-header">
      <div class="detail-ticker-symbol">${p(e.target_asset)}</div>
      <span class="detail-asset-type">${p(e.asset_type||"—")}</span>
    </div>
    <div class="detail-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Sentiment</div>
        <div class="detail-metric-value">
          <span class="sentiment-badge ${g}"><span class="sentiment-dot"></span>${g}</span>
          <span class="detail-metric-sub">${h}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Confidence</div>
        <div class="detail-metric-value detail-confidence">${c}%</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Risk Level</div>
        <div class="detail-metric-value">
          <span class="detail-risk ${o}">${p((e.risk_level||"—").toUpperCase())}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Tradeable</div>
        <div class="detail-metric-value">
          <span class="detail-tradeable ${f}">${d}</span>
        </div>
      </div>
    </div>
    <div class="detail-reasoning">
      <div class="detail-reasoning-label">Reasoning</div>
      <div class="detail-reasoning-text">${p(e.reasoning||"No reasoning provided.")}</div>
    </div>`}const a=t.querySelector(".detail-modal-body");a&&(a.innerHTML=i),t.classList.add("open")}function J(){n.detailModalOpen=!1,n.detailItem=null;const e=l("#detail-modal-overlay");e&&e.classList.remove("open")}async function De(e,t=""){const s=t.toUpperCase();n.companyProfileOpen=!0,n.companyProfileSymbol=e,n.companyProfileAssetType=s,n.companyProfileData=null,n.companyProfileLoading=!0,n.companyProfileFinancials=null,n.companyProfileCompetitors=null,n.companyProfileInstitutions=null,n.companyProfileInsiders=null;const c=s==="FUTURE"||s==="CURRENCY"?["overview"]:["fundamentals","financials","competitors","institutions","insiders"],r=c[0];n.companyProfileActiveTab=r,document.querySelectorAll(".cp-tab").forEach(g=>{g.style.display=c.includes(g.dataset.tab)?"":"none",g.classList.toggle("active",g.dataset.tab===r)});const o=l("#company-profile-panel");if(!o)return;const d=l("#company-profile-title");if(d){const g=s==="FUTURE"?" FUTURES":s==="CURRENCY"?" FX":"";d.textContent=`// ${e.toUpperCase()}${g}`}const f=l("#company-profile-body");f&&(f.innerHTML=`<div class="cp-spinner-wrap">
      <div class="cp-spinner"></div>
      <span class="cp-spinner-text">Loading${s==="FUTURE"?" contract":s==="CURRENCY"?" forex":" company"} data…</span>
    </div>`),o.classList.add("open"),document.querySelector(".dashboard").classList.add("cp-open"),s==="FUTURE"?Ct(e):s==="CURRENCY"?Et(e):Tt(e)}async function Tt(e){const t=l("#company-profile-body");if(t)try{const s=await k.fetch(`${S}/market/${encodeURIComponent(e)}/details`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileData=i,n.companyProfileLoading=!1,Ne(i)}catch(s){n.companyProfileLoading=!1,logger.warn("Error fetching company details for",e,s),t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load company details for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}function Ct(e){const t=l("#company-profile-body");if(!t)return;const s=Ve[e.toUpperCase()]||null,i=s?s.name:"Futures Contract",a=n.marketPrices[e];let c="";if(a&&a.price!=null){const o=a.change_percent||0,d=o>=0?"+":"",f=o>0?"price-up":o<0?"price-down":"price-flat";c=`
      <div class="cp-section">
        <div class="cp-section-title">CURRENT PRICE</div>
        <div class="cp-futures-price">
          <span class="cp-big-price ${f}">$${a.price.toFixed(2)}</span>
          <span class="ticker-change ${f}">${d}${o.toFixed(2)}%</span>
        </div>
      </div>`}let r="";s&&(r=`
      <div class="cp-section">
        <div class="cp-section-title">CONTRACT SPECIFICATIONS</div>
        <div class="cp-specs-grid">
          <div class="cp-spec"><span class="cp-spec-label">Exchange</span><span class="cp-spec-value">${p(s.exchange)}</span></div>
          <div class="cp-spec"><span class="cp-spec-label">Contract Unit</span><span class="cp-spec-value">${p(s.unit)}</span></div>
          <div class="cp-spec"><span class="cp-spec-label">Tick Size</span><span class="cp-spec-value">${p(s.tickSize)}</span></div>
          <div class="cp-spec"><span class="cp-spec-label">Trading Hours</span><span class="cp-spec-value">${p(s.hours)}</span></div>
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
    ${c}
    ${r}`,n.companyProfileLoading=!1}async function Et(e){const t=l("#company-profile-body");if(!t)return;const s=e.toUpperCase()+"/USD";try{const i=await k.fetch(`${S}/market/forex/${encodeURIComponent(e)}`);if(!i.ok){const f=await i.json().catch(()=>({}));throw new Error(f.message||`HTTP ${i.status}`)}const a=await i.json();n.companyProfileLoading=!1;const c=a.change_percent||0,r=c>=0?"+":"",o=c>0?"price-up":c<0?"price-down":"price-flat",d=a.day_high!=null&&a.day_low!=null?`<div class="cp-section">
          <div class="cp-section-title">DAY RANGE</div>
          <div class="cp-range">${a.day_low.toFixed(4)} — ${a.day_high.toFixed(4)}</div>
        </div>`:"";t.innerHTML=`
      <div class="cp-instrument-header">
        <div class="cp-instrument-icon">¤</div>
        <div>
          <div class="cp-instrument-name">${p(s)}</div>
          <div class="cp-instrument-meta">
            <span class="cp-instrument-symbol">${p(e.toUpperCase())}</span>
            <span class="cp-instrument-type">CURRENCY</span>
          </div>
        </div>
      </div>
      <div class="cp-section">
        <div class="cp-section-title">EXCHANGE RATE</div>
        <div class="cp-futures-price">
          <span class="cp-big-price ${o}">${a.price!=null?a.price.toFixed(4):"—"}</span>
          <span class="ticker-change ${o}">${r}${c.toFixed(2)}%</span>
        </div>
      </div>
      ${d}`}catch(i){n.companyProfileLoading=!1,logger.warn("Error fetching forex data for",e,i),t.innerHTML=`<div class="cp-error">
      <div class="cp-error-icon">¤</div>
      <p>Currency data not available for <strong>${p(e.toUpperCase())}</strong></p>
      <span>${p(i.message)}</span>
    </div>`}}function Ne(e){const t=l("#company-profile-body");if(!t)return;const s=e.logo_url?`<img class="cp-logo" src="${p(e.logo_url)}" alt="${p(e.name)}" onerror="this.style.display='none'">`:"",i=e.homepage_url?`<a class="cp-homepage" href="${p(e.homepage_url)}" target="_blank" rel="noopener noreferrer">${p(e.homepage_url.replace(/^https?:\/\//,""))}</a>`:"";t.innerHTML=`
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
        <div class="detail-metric-value">${Ye(e.market_cap)}</div>
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
  `}function be(){n.companyProfileOpen=!1,n.companyProfileSymbol=null,n.companyProfileData=null,n.companyProfileLoading=!1,n.companyProfileActiveTab="fundamentals",n.companyProfileFinancials=null,n.companyProfileCompetitors=null,n.companyProfileInstitutions=null,n.companyProfileInsiders=null;const e=l("#company-profile-panel");e&&e.classList.remove("open");const t=document.querySelector(".dashboard");t&&t.classList.remove("cp-open")}async function St(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileFinancials){we(n.companyProfileFinancials);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading financials…</span>
  </div>`;try{const s=await k.fetch(`${S}/market/${encodeURIComponent(e)}/financials`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileFinancials=i,n.companyProfileActiveTab==="financials"&&we(i)}catch(s){logger.warn("Error fetching financials for",e,s),n.companyProfileActiveTab==="financials"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load financial data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function U(e){if(e==null)return"—";const t=Math.abs(e),s=e<0?"-":"";return t>=1e12?s+"$"+(t/1e12).toFixed(2)+"T":t>=1e9?s+"$"+(t/1e9).toFixed(2)+"B":t>=1e6?s+"$"+(t/1e6).toFixed(2)+"M":t>=1e3?s+"$"+(t/1e3).toFixed(2)+"K":s+"$"+t.toFixed(2)}function we(e){const t=l("#company-profile-body");if(!t)return;const s=e.financials,i=e.earnings||[],a=s&&(s.revenue!=null||s.net_income!=null||s.eps!=null),c=i.length>0&&i.some(f=>f.actual_eps!=null);if(!a&&!c){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No financial data available</p>
      <span>Financial data is not available for this ticker (e.g., ETFs, indices).</span>
    </div>`;return}const r=s&&s.fiscal_period&&s.fiscal_year?`${s.fiscal_period} ${s.fiscal_year}`:"",o=a?`
    ${r?`<div class="cp-fin-period">Latest Quarter: ${p(r)}</div>`:""}
    <div class="cp-fin-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Revenue</div>
        <div class="detail-metric-value">${U(s.revenue)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Net Income</div>
        <div class="detail-metric-value">${U(s.net_income)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">EPS</div>
        <div class="detail-metric-value">${s.eps!=null?"$"+s.eps.toFixed(2):"—"}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">P/E Ratio</div>
        <div class="detail-metric-value">${s.pe_ratio!=null?s.pe_ratio.toFixed(1)+"x":"—"}</div>
      </div>
    </div>`:"";let d="";if(c){const f=[...i].reverse(),g=Math.max(...f.map(m=>Math.abs(m.actual_eps||0)),.01);d=`
    <div class="cp-fin-chart-section">
      <div class="cp-desc-label">Earnings Per Share — Last 4 Quarters</div>
      <div class="cp-bar-chart">${f.map(m=>{const w=m.actual_eps;if(w==null)return"";const L=Math.min(Math.abs(w)/g*100,100),I=w>=0?"cp-bar-positive":"cp-bar-negative",b=`${m.fiscal_period} ${String(m.fiscal_year).slice(-2)}`,C=m.estimated_eps!=null,y=C&&w>=m.estimated_eps,$=C?y?"cp-bar-beat":"cp-bar-miss":I;return`<div class="cp-bar-col">
        <div class="cp-bar-value ${$}">$${w.toFixed(2)}</div>
        <div class="cp-bar-track">
          <div class="cp-bar-fill ${$}" style="height:${L}%"></div>
        </div>
        <div class="cp-bar-label">${p(b)}</div>
        ${C?`<div class="cp-bar-est">Est: $${m.estimated_eps.toFixed(2)}</div>`:""}
      </div>`}).join("")}</div>
      <div class="cp-bar-legend">
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-positive"></span>Positive</span>
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-negative"></span>Negative</span>
      </div>
    </div>`}t.innerHTML=o+d}async function xt(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileCompetitors){$e(n.companyProfileCompetitors);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading competitors…</span>
  </div>`;try{const s=await k.fetch(`${S}/market/${encodeURIComponent(e)}/competitors`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileCompetitors=i,n.companyProfileActiveTab==="competitors"&&$e(i)}catch(s){logger.warn("Error fetching competitors for",e,s),n.companyProfileActiveTab==="competitors"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load competitor data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function $e(e){const t=l("#company-profile-body");if(!t)return;const s=e.competitors||[];if(s.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No competitor data available</p>
      <span>Competitor information is not available for this ticker.</span>
    </div>`;return}const i=s.map(a=>{const c=a.change_percent!=null?a.change_percent:null,r=c!=null?c>=0?"positive":"negative":"",o=c!=null?`${c>=0?"+":""}${c.toFixed(2)}%`:"—",d=a.price!=null?`$${a.price.toFixed(2)}`:"—",f=U(a.market_cap),g=a.sector||"—";return`<tr class="cp-comp-row">
      <td class="cp-comp-ticker"><span class="cp-comp-ticker-link" data-ticker="${p(a.symbol)}">${p(a.symbol)}</span></td>
      <td class="cp-comp-name">${p(a.name)}</td>
      <td class="cp-comp-mcap">${f}</td>
      <td class="cp-comp-price">${d}</td>
      <td class="cp-comp-change ${r}">${o}</td>
      <td class="cp-comp-sector">${p(g)}</td>
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
    </div>`,t.querySelectorAll(".cp-comp-ticker-link[data-ticker]").forEach(a=>{a.addEventListener("click",()=>{De(a.dataset.ticker)})})}const ke="inst_tooltip_dismissed";function A(e){if(e==null)return"—";const t=Math.abs(e);return t>=1e9?(t/1e9).toFixed(2)+"B":t>=1e6?(t/1e6).toFixed(2)+"M":t>=1e3?(t/1e3).toFixed(1)+"K":t.toLocaleString()}async function Lt(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileInstitutions){Te(n.companyProfileInstitutions);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading institutional data…</span>
  </div>`;try{const s=await k.fetch(`${S}/market/${encodeURIComponent(e)}/institutions`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileInstitutions=i,n.companyProfileActiveTab==="institutions"&&Te(i)}catch(s){logger.warn("Error fetching institutions for",e,s),n.companyProfileActiveTab==="institutions"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load institutional data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function Te(e){const t=l("#company-profile-body");if(!t)return;const s=e.institutional_holders||[],i=e.major_position_changes||[];if(s.length===0&&i.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No institutional data available</p>
      <span>Institutional holdings data is not available for this ticker.</span>
    </div>`;return}const a=s.length>0?s[0].report_date:null,c=a?`<div class="cp-inst-date-banner">Holdings as of ${p(a)}</div>`:"",o=localStorage.getItem(ke)?"":`<div class="cp-inst-tooltip" id="cp-inst-tooltip">
    <div class="cp-inst-tooltip-text">
      <strong>About this data:</strong> 13F holdings are filed quarterly (up to 45 days after quarter end).
      13D/13G filings are filed in near-real-time when an investor crosses the 5% ownership threshold.
    </div>
    <button class="cp-inst-tooltip-dismiss" id="cp-inst-tooltip-dismiss">✕</button>
  </div>`;let d=0,f=0;s.forEach(y=>{y.value!=null&&(d+=y.value),y.shares_held!=null&&(f+=y.shares_held)});const g=`<div class="cp-inst-summary">
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Institutions Reporting</span>
      <span class="cp-inst-summary-value">${s.length}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Institutional Value</span>
      <span class="cp-inst-summary-value">${U(d)}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Shares Held</span>
      <span class="cp-inst-summary-value">${A(f)}</span>
    </div>
  </div>`,h=s.map(y=>{const $=A(y.shares_held),O=U(y.value),_=y.change_type||"held";let E="";return _==="new"?E='<span class="cp-inst-badge cp-inst-badge-new">NEW</span>':_==="increased"?E='<span class="cp-inst-change-up">▲</span>':_==="decreased"?E='<span class="cp-inst-change-down">▼</span>':E='<span class="cp-inst-change-flat">—</span>',`<tr class="cp-inst-row">
      <td class="cp-inst-name">${p(y.institution_name||"Unknown")}</td>
      <td class="cp-inst-shares">${$}</td>
      <td class="cp-inst-value">${O}</td>
      <td class="cp-inst-change">${E}</td>
    </tr>`}).join(""),m=s.length>0?`
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
    </div>`:"",w=Date.now(),L=720*60*60*1e3,R=i.map(y=>{const $=y.filing_date||"",_=$&&w-new Date($).getTime()<L?'<span class="cp-inst-badge cp-inst-badge-new">NEW</span> ':"",E=y.percent_owned!=null?y.percent_owned.toFixed(2)+"%":"—",D=y.filing_type||"";return`<tr class="cp-inst-row ${D.includes("13D")?"cp-inst-13d":"cp-inst-13g"}">
      <td class="cp-inst-filer">${_}${p(y.filer_name||"Unknown")}</td>
      <td class="cp-inst-pct">${E}</td>
      <td class="cp-inst-filing-date">${p($)}</td>
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
        <tbody>${R}</tbody>
      </table>
    </div>`:"",b='<div class="cp-inst-source">Source: SEC EDGAR (13F quarterly + 13D/13G real-time filings)</div>';t.innerHTML=c+o+g+m+I+b;const C=document.getElementById("cp-inst-tooltip-dismiss");C&&C.addEventListener("click",()=>{localStorage.setItem(ke,"1");const y=document.getElementById("cp-inst-tooltip");y&&y.remove()})}async function _t(e){if(!e)return;const t=l("#company-profile-body");if(t){if(n.companyProfileInsiders){Ce(n.companyProfileInsiders);return}t.innerHTML=`<div class="cp-spinner-wrap">
    <div class="cp-spinner"></div>
    <span class="cp-spinner-text">Loading insider transactions…</span>
  </div>`;try{const s=await k.fetch(`${S}/market/${encodeURIComponent(e)}/insiders`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileInsiders=i,n.companyProfileActiveTab==="insiders"&&Ce(i)}catch(s){logger.warn("Error fetching insiders for",e,s),n.companyProfileActiveTab==="insiders"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load insider trading data for <strong>${p(e)}</strong></p>
        <span>${p(s.message)}</span>
      </div>`)}}}function Ce(e){const t=l("#company-profile-body");if(!t)return;const s=e.insider_transactions||[];if(s.length===0){t.innerHTML=`<div class="cp-error">
      <div class="cp-error-icon">—</div>
      <p>No insider transaction data available for <strong>${p(e.symbol||"")}</strong></p>
    </div>`;return}const i=Date.now()-2160*60*60*1e3;let a=0,c=0,r=0,o=0;for(const b of s){if((b.filing_date?new Date(b.filing_date).getTime():0)<i)continue;const y=(b.transaction_type||"").toLowerCase(),$=Math.abs(b.total_value||0);y==="purchase"?(a+=$,r++):y==="sale"&&(c+=$,o++)}const d=a-c,f=d>0?"cp-insider-sentiment-buy":d<0?"cp-insider-sentiment-sell":"cp-insider-sentiment-neutral",g=d>0?"Net Buying":d<0?"Net Selling":"Neutral",h=d>0?"▲":d<0?"▼":"●",m=`<div class="cp-insider-sentiment ${f}">
    <div class="cp-insider-sentiment-header">
      <span class="cp-insider-sentiment-icon">${h}</span>
      <span class="cp-insider-sentiment-label">${g}</span>
      <span class="cp-insider-sentiment-period">90-day insider activity</span>
    </div>
    <div class="cp-insider-sentiment-stats">
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-buy-text">${r} buys</span>
        <span class="cp-insider-stat-amount">$${A(a)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-sell-text">${o} sells</span>
        <span class="cp-insider-stat-amount">$${A(c)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value">Net</span>
        <span class="cp-insider-stat-amount ${f}">${d>=0?"+":""}$${A(Math.abs(d))}</span>
      </div>
    </div>
  </div>`,R=`<div class="cp-insider-table-wrap">
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
      <tbody>${[...s].sort((b,C)=>{const y=b.filing_date||"";return(C.filing_date||"").localeCompare(y)}).map(b=>{const C=(b.transaction_type||"").toLowerCase();let y="cp-insider-row-other";C==="purchase"?y="cp-insider-row-buy":C==="sale"?y="cp-insider-row-sell":C==="option exercise"&&(y="cp-insider-row-exercise");const $=b.shares!=null?A(b.shares):"—",O=b.price_per_share!=null?"$"+b.price_per_share.toFixed(2):"—",_=b.total_value!=null?"$"+A(b.total_value):"—",E=b.shares_held_after!=null?A(b.shares_held_after):"—";return`<tr class="cp-insider-row ${y}">
      <td class="cp-insider-date">${p(b.filing_date||"")}</td>
      <td class="cp-insider-name">${p(b.insider_name||"Unknown")}</td>
      <td class="cp-insider-title">${p(b.title||"")}</td>
      <td class="cp-insider-type">${p(b.transaction_type||"")}</td>
      <td class="cp-insider-shares">${$}</td>
      <td class="cp-insider-price">${O}</td>
      <td class="cp-insider-total">${_}</td>
      <td class="cp-insider-holdings">${E}</td>
    </tr>`}).join("")}</tbody>
    </table>
  </div>`,I='<div class="cp-insider-source">Source: SEC EDGAR Form 4 (filed within 2 business days of transaction)</div>';t.innerHTML=m+R+I}function Mt(){if(typeof k>"u")return;k.init();const e=l("#btn-signin");e&&e.addEventListener("click",()=>{k.showAuthModal("signin")});const t=l("#btn-signout");t&&t.addEventListener("click",()=>{k.signOut()});const s=l("#btn-user"),i=l("#user-dropdown");s&&i&&(s.addEventListener("click",a=>{a.stopPropagation(),i.classList.toggle("open")}),document.addEventListener("click",()=>{i.classList.remove("open")})),k.onAuthChange(a=>{It(a)})}function It(e){const t=l("#btn-signin"),s=l("#user-menu");if(e){t&&(t.style.display="none"),s&&(s.style.display="flex");const i=l("#user-avatar"),a=l("#user-name"),c=l("#dropdown-email");i&&e.photoURL&&(i.src=e.photoURL,i.alt=e.displayName||""),a&&(a.textContent=e.displayName||e.email||""),c&&(c.textContent=e.email||""),Ft()}else t&&(t.style.display="flex"),s&&(s.style.display="none"),Ue()}async function Ft(){try{const e=await k.fetch(`${S}/auth/tier`);if(!e.ok)return;const t=await e.json(),s=t.tier||"free",i=s==="plus"?"pro":s,a=t.features||{};n.userTier=i,n.userFeatures=a,Y(),H(),await F(),ie(),Xe();const c=l("#tier-badge"),r=l("#dropdown-tier");if(c&&(c.textContent=i.toUpperCase(),c.className="tier-badge"+(i!=="free"?" "+i:"")),r){const o={free:"Free Plan",pro:"Pro Plan",plus:"Pro Plan"};r.textContent=o[i]||"Free Plan"}a.terminal_access===!1||i==="free"?Ue():(Pt(),st())}catch{}}function Ue(){if(l("#upgrade-gate"))return;const e=document.createElement("div");e.id="upgrade-gate",e.style.cssText="position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(1,4,9,0.95);",e.innerHTML='<div style="text-align:center;max-width:420px;padding:40px;border:1px solid rgba(48,54,61,0.8);border-radius:12px;background:#0d1117;"><h2 style="color:#e6edf3;margin:0 0 12px;font-size:22px;">Upgrade to Pro</h2><p style="color:#8b949e;margin:0 0 24px;line-height:1.6;">The SIGNAL terminal requires a Pro subscription. Get full access to real-time news, sentiment analysis, and deduplication.</p><a href="/pricing" style="display:inline-block;padding:10px 28px;background:#238636;color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">View Plans</a><div style="margin-top:16px;"><a href="/" style="color:#8b949e;font-size:13px;text-decoration:underline;">Back to home</a></div></div>',document.body.appendChild(e),Oe(),_e()}function Pt(){const e=l("#upgrade-gate");e&&e.remove()}function At(){if(l("#max-upgrade-prompt"))return;const e=document.createElement("div");e.id="max-upgrade-prompt",e.className="modal-overlay open",e.innerHTML='<div class="modal" style="width:min(420px,90vw);text-align:center;padding:32px;"><div style="font-size:28px;margin-bottom:12px;">🚀</div><h2 style="color:var(--text-primary);margin:0 0 12px;font-size:18px;">Upgrade to Max</h2><p style="color:var(--text-secondary);margin:0 0 8px;line-height:1.5;font-size:13px;">AI-powered ticker recommendations, confidence scores, risk levels, and real-time market data are exclusive to the <strong>Max</strong> plan.</p><p style="color:var(--text-muted);margin:0 0 24px;font-size:12px;">Unlock the full trading terminal experience.</p><a href="/pricing" style="display:inline-block;padding:10px 28px;background:var(--blue);color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">View Max Plan</a><div style="margin-top:12px;"><button id="max-upgrade-dismiss" style="background:none;border:none;color:var(--text-muted);font-size:13px;cursor:pointer;padding:8px;">Maybe later</button></div></div>',e.addEventListener("click",t=>{(t.target===e||t.target.id==="max-upgrade-dismiss")&&e.remove()}),document.body.appendChild(e)}function Ee(){Qe(),Ze(),et(),H(),dt(),He(),$t(),ye(),Mt(),setInterval(ye,1e3),F(),Q(),de(),Re(),setInterval(()=>{Q(),de()},3e4)}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",Ee):Ee();document.addEventListener("DOMContentLoaded",function(){var e=document.getElementById("auth-gate"),t=document.getElementById("auth-gate-signin");function s(){typeof SignalAuth<"u"&&SignalAuth.isSignedIn()?e.classList.add("hidden"):e.classList.remove("hidden")}t&&t.addEventListener("click",function(){typeof SignalAuth<"u"&&SignalAuth.showAuthModal("signin")}),typeof SignalAuth<"u"&&SignalAuth.onAuthChange(s),setTimeout(function(){typeof SignalAuth<"u"&&(SignalAuth.onAuthChange(s),s())},500)});

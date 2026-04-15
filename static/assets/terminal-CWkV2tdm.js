import{S as L}from"./auth-C4Y_TkCR.js";/* empty css             *//* empty css                 */const C="/api",Le=200,Te=6e4,Ce=1e4,K=10,M=[{id:"time",label:"Time",defaultVisible:!0,required:!1,requiredFeature:null},{id:"sentiment",label:"Sentiment",defaultVisible:!0,required:!1,requiredFeature:"sentiment_filter"},{id:"source",label:"Source",defaultVisible:!0,required:!1,requiredFeature:null},{id:"headline",label:"Headline",defaultVisible:!0,required:!0,requiredFeature:null},{id:"summary",label:"Summary",defaultVisible:!0,required:!1,requiredFeature:null},{id:"ticker",label:"Ticker",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"confidence",label:"Confidence",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"risk",label:"Risk Level",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"tradeable",label:"Tradeable",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"}],le="instnews_column_visibility",ce="instnews_column_order",de="instnews_column_widths",N=60;let s={items:[],seenIds:new Set,newIds:new Set,sources:[],stats:null,filter:{sentiment:"all",sources:new Set,query:"",dateFrom:"",dateTo:"",hideDuplicates:!1},refreshInterval:5e3,refreshTimer:null,lastRefresh:null,connected:!1,loading:!0,totalFetched:0,fetchCount:0,itemsPerSecond:0,startTime:Date.now(),sidebarOpen:!1,modalOpen:!1,detailModalOpen:!1,detailItem:null,userTier:null,userFeatures:{},soundEnabled:!1,columnVisibility:{},columnOrder:M.map(e=>e.id),columnWidths:{},columnSettingsOpen:!1,marketPrices:{},priceRefreshTimer:null,companyProfileOpen:!1,companyProfileSymbol:null,companyProfileData:null,companyProfileLoading:!1,companyProfileActiveTab:"fundamentals",companyProfileFinancials:null,companyProfileCompetitors:null,companyProfileInstitutions:null,companyProfileInsiders:null};const l=e=>document.querySelector(e),F=e=>[...document.querySelectorAll(e)];function z(e){if(!e)return"--:--:--";try{const t=new Date(e);return isNaN(t.getTime())?"--:--:--":t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"})}catch{return"--:--:--"}}function pe(e){if(!e)return"";try{const t=new Date(e),i=new Date-t;return i<0?"just now":i<6e4?`${Math.floor(i/1e3)}s ago`:i<36e5?`${Math.floor(i/6e4)}m ago`:i<864e5?`${Math.floor(i/36e5)}h ago`:`${Math.floor(i/864e5)}d ago`}catch{return""}}function Ee(e){if(!e)return!1;try{const t=new Date(e);return Date.now()-t.getTime()<Te}catch{return!1}}function p(e){const t=document.createElement("div");return t.textContent=e,t.innerHTML}function Se(e,t){return e?e.length>t?e.slice(0,t)+"…":e:""}function _e(e){return e==null?"—":e>=1e12?"$"+(e/1e12).toFixed(2)+"T":e>=1e9?"$"+(e/1e9).toFixed(2)+"B":e>=1e6?"$"+(e/1e6).toFixed(2)+"M":"$"+e.toLocaleString()}async function A(){try{const e=new URLSearchParams({limit:Le});s.filter.dateFrom&&e.set("from",s.filter.dateFrom),s.filter.dateTo&&e.set("to",s.filter.dateTo);const t=await L.fetch(`${C}/news?${e}`);if(!t.ok)throw new Error(`HTTP ${t.status}`);const n=await t.json();if(s.connected=!0,s.loading=!1,s.fetchCount++,s.lastRefresh=new Date().toISOString(),n.items&&n.items.length>0){const i=new Set;for(const r of n.items)s.seenIds.has(r.id)||(i.add(r.id),s.seenIds.add(r.id));s.soundEnabled&&i.size>0&&s.fetchCount>1&&Me(),s.newIds=i,s.items=n.items,s.totalFetched=n.count;const a=(Date.now()-s.startTime)/1e3;s.itemsPerSecond=a>0?(s.totalFetched/a).toFixed(1):0}T(),Ye(),ee(!0),G()}catch{s.connected=!1,s.loading=!1,ee(!1),s.items.length===0&&Ue("Unable to connect to API. Retrying...")}}async function J(){try{const e=await L.fetch(`${C}/sources`);if(!e.ok)return;const t=await e.json();s.sources=t.sources||[],ye()}catch{}}async function W(){try{const e=await L.fetch(`${C}/stats`);if(!e.ok)return;s.stats=await e.json(),Ge()}catch{}}async function G(){if(!s.userFeatures.ai_ticker_recommendations||!s.columnVisibility.ticker)return;const e=[...new Set(s.items.map(t=>t.target_asset).filter(Boolean))];if(e.length!==0){for(let t=0;t<e.length;t+=K){const i=e.slice(t,t+K).map(async a=>{try{const r=await L.fetch(`${C}/market/${encodeURIComponent(a)}`);r.ok&&(s.marketPrices[a]=await r.json())}catch{}});await Promise.all(i)}T()}}function Pe(){ue(),s.userFeatures.ai_ticker_recommendations&&s.columnVisibility.ticker&&(s.priceRefreshTimer=setInterval(G,Ce))}function ue(){s.priceRefreshTimer&&(clearInterval(s.priceRefreshTimer),s.priceRefreshTimer=null)}async function Q(){try{const e=l("#btn-refresh");e&&(e.disabled=!0,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>Refreshing'),await L.fetch(`${C}/refresh`,{method:"POST"}),await A(),await W(),e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}catch{const e=l("#btn-refresh");e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}}function Me(){try{const e=new(window.AudioContext||window.webkitAudioContext),t=e.createOscillator(),n=e.createGain();t.connect(n),n.connect(e.destination),t.type="sine",t.frequency.setValueAtTime(880,e.currentTime),t.frequency.setValueAtTime(1100,e.currentTime+.05),n.gain.setValueAtTime(.08,e.currentTime),n.gain.exponentialRampToValueAtTime(.001,e.currentTime+.15),t.start(e.currentTime),t.stop(e.currentTime+.15)}catch{}}function fe(){return s.items.filter(e=>{if(s.filter.sentiment!=="all"&&e.sentiment_label!==s.filter.sentiment||s.filter.sources.size>0&&!s.filter.sources.has(e.source))return!1;if(s.filter.query){const t=s.filter.query.toLowerCase(),n=(e.title||"").toLowerCase().includes(t),i=(e.summary||"").toLowerCase().includes(t);if(!n&&!i)return!1}return!(s.filter.hideDuplicates&&e.duplicate)})}function Ie(){const e={all:0,bullish:0,bearish:0,neutral:0};for(const t of s.items)e.all++,e[t.sentiment_label]!==void 0&&e[t.sentiment_label]++;return e}function Ae(){try{const t=localStorage.getItem(le);if(t){const n=JSON.parse(t),i={};for(const a of M)i[a.id]=a.id in n?n[a.id]:a.defaultVisible;s.columnVisibility=i;return}}catch{}const e={};for(const t of M)e[t.id]=t.defaultVisible;s.columnVisibility=e}function Fe(){try{localStorage.setItem(le,JSON.stringify(s.columnVisibility))}catch{}}function He(){try{const e=localStorage.getItem(ce);if(e){const t=JSON.parse(e);if(Array.isArray(t)){const n=new Set(M.map(a=>a.id)),i=t.filter(a=>n.has(a));for(const a of M)i.includes(a.id)||i.push(a.id);s.columnOrder=i;return}}}catch{}s.columnOrder=M.map(e=>e.id)}function me(){try{localStorage.setItem(ce,JSON.stringify(s.columnOrder))}catch{}}function De(){try{const e=localStorage.getItem(de);if(e){const t=JSON.parse(e);if(t&&typeof t=="object"){const n={};for(const i of M)i.id in t&&typeof t[i.id]=="number"&&t[i.id]>=N&&(n[i.id]=t[i.id]);s.columnWidths=n;return}}}catch{}s.columnWidths={}}function ve(){try{localStorage.setItem(de,JSON.stringify(s.columnWidths))}catch{}}function he(){const e={};for(const t of M)e[t.id]=t;return s.columnOrder.map(t=>e[t]).filter(Boolean)}function ge(e){return!e.requiredFeature||s.userTier===null?!1:!s.userFeatures[e.requiredFeature]}function D(){return he().filter(e=>ge(e)?!1:s.columnVisibility[e.id]!==!1)}function I(){const e=document.querySelector(".news-table thead");if(!e)return;const t=D();e.innerHTML="<tr>"+t.map(i=>{const a=s.columnWidths[i.id],r=a?` style="width:${a}px"`:"";return`<th class="col-${i.id}" draggable="true" data-col-id="${i.id}"${r}><span class="th-drag-label">${i.label}</span><span class="col-resize-handle" data-col-id="${i.id}"></span></th>`}).join("")+"</tr>";const n=document.querySelector(".news-table");n&&(n.style.tableLayout=Object.keys(s.columnWidths).length>0?"fixed":""),qe(),Oe()}function Oe(){const e=document.querySelector(".news-table thead tr");if(!e)return;const t=e.querySelectorAll("th[draggable]");let n=null;t.forEach(i=>{i.addEventListener("dragstart",a=>{if(a.target.closest(".col-resize-handle")){a.preventDefault();return}n=i,i.classList.add("th-dragging"),a.dataTransfer.effectAllowed="move",a.dataTransfer.setData("text/plain",i.dataset.colId)}),i.addEventListener("dragover",a=>{if(a.preventDefault(),a.dataTransfer.dropEffect="move",!n||i===n)return;e.querySelectorAll("th").forEach(c=>c.classList.remove("th-drag-over-left","th-drag-over-right"));const r=i.getBoundingClientRect(),o=r.left+r.width/2;a.clientX<o?i.classList.add("th-drag-over-left"):i.classList.add("th-drag-over-right")}),i.addEventListener("dragleave",()=>{i.classList.remove("th-drag-over-left","th-drag-over-right")}),i.addEventListener("drop",a=>{if(a.preventDefault(),a.stopPropagation(),!n||i===n)return;e.querySelectorAll("th").forEach(w=>w.classList.remove("th-drag-over-left","th-drag-over-right"));const r=n.dataset.colId,o=i.dataset.colId,c=[...s.columnOrder],u=c.indexOf(r),f=c.indexOf(o);if(u===-1||f===-1)return;c.splice(u,1);const y=i.getBoundingClientRect(),g=y.left+y.width/2,v=a.clientX<g?c.indexOf(o):c.indexOf(o)+1;c.splice(v,0,r),s.columnOrder=c,me(),I(),T(),s.columnSettingsOpen&&Y()}),i.addEventListener("dragend",()=>{i.classList.remove("th-dragging"),e.querySelectorAll("th").forEach(a=>a.classList.remove("th-drag-over-left","th-drag-over-right"))})})}function qe(){document.querySelectorAll(".col-resize-handle").forEach(t=>{t.addEventListener("mousedown",Re),t.addEventListener("dblclick",Ne)})}function Re(e){e.preventDefault(),e.stopPropagation();const t=e.target,n=t.parentElement,i=t.dataset.colId,a=e.clientX,r=n.offsetWidth,o=document.querySelector(".news-table");o&&(o.style.tableLayout="fixed");const c=[...document.querySelectorAll(".news-table thead th")];let u=0;c.forEach(g=>{const v=g.offsetWidth;g.style.width=v+"px",u+=v}),o&&(o.style.width=u+"px"),document.body.style.cursor="col-resize",document.body.style.userSelect="none",t.classList.add("active");function f(g){const v=g.clientX-a,w=Math.max(N,r+v);n.style.width=w+"px",o&&(o.style.width=u+(w-r)+"px")}function y(g){document.removeEventListener("mousemove",f),document.removeEventListener("mouseup",y),document.body.style.cursor="",document.body.style.userSelect="",t.classList.remove("active"),c.forEach(w=>{const E=w.dataset.colId;E&&(s.columnWidths[E]=w.offsetWidth)});const v=g.clientX-a;s.columnWidths[i]=Math.max(N,r+v),o&&(o.style.width=""),ve(),I(),T()}document.addEventListener("mousemove",f),document.addEventListener("mouseup",y)}function Ne(e){e.preventDefault(),e.stopPropagation();const t=e.target.dataset.colId,i=D().findIndex(f=>f.id===t);if(i===-1)return;const a=document.querySelectorAll("#news-body tr");let r=N;const o=e.target.parentElement,c=document.createElement("span");c.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;",c.textContent=o.textContent,document.body.appendChild(c),r=Math.max(r,c.offsetWidth+32),document.body.removeChild(c),a.forEach(f=>{if(f.classList.contains("skeleton-row"))return;const g=f.querySelectorAll("td")[i];if(!g)return;const v=document.createElement("div");v.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:12px;",v.innerHTML=g.innerHTML,document.body.appendChild(v),r=Math.max(r,v.offsetWidth+24),document.body.removeChild(v)}),r=Math.min(r,600);const u=document.querySelector(".news-table");u&&(u.style.tableLayout="fixed"),s.columnWidths[t]=r,ve(),I(),T()}function Be(e,t,n,i){switch(e){case"time":return`<td class="cell-time" title="${pe(t.published)}">${z(t.published)}</td>`;case"sentiment":return`<td class="cell-sentiment"><span class="sentiment-badge ${t.sentiment_label}"><span class="sentiment-dot"></span>${t.sentiment_label}</span></td>`;case"source":return`<td class="cell-source"><span class="source-tag">${p(t.source||"")}</span></td>`;case"headline":return`<td class="cell-headline"><a href="${p(t.link||"#")}" target="_blank" rel="noopener noreferrer">${p(t.title||"Untitled")}</a>${n?'<span class="badge-new">NEW</span>':""}${i}</td>`;case"summary":return`<td class="cell-summary">${p(Se(t.summary,120))}</td>`;case"ticker":{if(!t.target_asset)return'<td class="cell-ticker"><span class="cell-dash">—</span></td>';const a=p(t.target_asset),r=s.marketPrices[t.target_asset];let o="";if(r&&r.price!=null){const c=r.change_percent||0,u=c>=0?"+":"";o=`<span class="ticker-price ${c>0?"price-up":c<0?"price-down":"price-flat"}">$${r.price.toFixed(2)} <span class="ticker-change">${u}${c.toFixed(2)}%</span></span>`}return`<td class="cell-ticker"><span class="ticker-badge" data-ticker="${a}">${a}${o}</span></td>`}case"confidence":return`<td class="cell-confidence">${t.confidence!=null?Math.round(t.confidence*100)+"%":'<span class="cell-dash">—</span>'}</td>`;case"risk":{if(!t.risk_level)return'<td class="cell-risk"><span class="cell-dash">—</span></td>';const a=t.risk_level.toLowerCase();return`<td class="cell-risk"><span class="risk-badge ${a==="low"?"green":a==="high"?"red":"yellow"}">${p(t.risk_level.toUpperCase())}</span></td>`}case"tradeable":return t.tradeable==null?'<td class="cell-tradeable"><span class="cell-dash">—</span></td>':`<td class="cell-tradeable"><span class="tradeable-badge ${t.tradeable?"yes":"no"}">${t.tradeable?"YES":"NO"}</span></td>`;default:return"<td></td>"}}function Z(e){const t=typeof e=="boolean"?e:!s.columnSettingsOpen;s.columnSettingsOpen=t;const n=l("#column-settings-panel");n&&n.classList.toggle("open",t)}function Y(){const e=l("#column-settings-panel");if(!e)return;const n=he().map(o=>{const c=ge(o),u=!c&&s.columnVisibility[o.id]!==!1,f=o.required||c;return`<div class="col-toggle-item${c?" locked":""}${o.required?" required":""}" draggable="true" data-col-id="${o.id}">
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
    <div class="col-settings-list">${n.join("")}</div>`,e.querySelectorAll('input[type="checkbox"]').forEach(o=>{o.addEventListener("change",c=>{const u=c.target.dataset.colId;s.columnVisibility[u]=c.target.checked,Fe(),I(),T()})});const i=e.querySelector(".col-settings-list");let a=null,r=!1;i.querySelectorAll(".col-drag-handle").forEach(o=>{o.addEventListener("mousedown",()=>{r=!0})}),document.addEventListener("mouseup",()=>{r=!1},{once:!1}),i.querySelectorAll(".col-toggle-item[draggable]").forEach(o=>{o.addEventListener("dragstart",c=>{if(!r){c.preventDefault();return}a=o,s._dragging=!0,o.classList.add("dragging"),c.dataTransfer.effectAllowed="move",c.dataTransfer.setData("text/plain",o.dataset.colId)}),o.addEventListener("dragover",c=>{if(c.preventDefault(),c.dataTransfer.dropEffect="move",!a||o===a)return;i.querySelectorAll(".col-toggle-item").forEach(y=>y.classList.remove("drag-over-above","drag-over-below"));const u=o.getBoundingClientRect(),f=u.top+u.height/2;c.clientY<f?o.classList.add("drag-over-above"):o.classList.add("drag-over-below")}),o.addEventListener("dragleave",()=>{o.classList.remove("drag-over-above","drag-over-below")}),o.addEventListener("drop",c=>{if(c.preventDefault(),c.stopPropagation(),!a||o===a)return;i.querySelectorAll(".col-toggle-item").forEach(g=>g.classList.remove("drag-over-above","drag-over-below"));const u=o.getBoundingClientRect(),f=u.top+u.height/2;c.clientY<f?i.insertBefore(a,o):i.insertBefore(a,o.nextSibling);const y=[...i.querySelectorAll(".col-toggle-item[data-col-id]")].map(g=>g.dataset.colId);s.columnOrder=y,me(),I(),T()}),o.addEventListener("dragend",()=>{o.classList.remove("dragging"),s._dragging=!1,i.querySelectorAll(".col-toggle-item").forEach(c=>c.classList.remove("drag-over-above","drag-over-below"))})}),i.addEventListener("dragover",o=>{o.preventDefault()})}function T(){const e=l("#news-body");if(!e)return;const t=fe(),n=D(),i=n.length;if(t.length===0&&!s.loading){e.innerHTML=`
      <tr>
        <td colspan="${i}">
          <div class="empty-state">
            <div class="icon">◇</div>
            <div>No items match current filters</div>
            <div style="font-size:11px">Try adjusting sentiment or source filters</div>
          </div>
        </td>
      </tr>`;return}const a=t.map(r=>{const o=s.newIds.has(r.id),c=Ee(r.fetched_at),u=o?"news-row-new":"",f=r.duplicate?'<span class="badge-dup">DUP</span>':"",y=n.map(g=>Be(g.id,r,c,f)).join("");return`<tr class="${u}" data-id="${r.id}">${y}</tr>`});e.innerHTML=a.join(""),We(),ze()}function Ve(){const e=l("#news-body");if(!e)return;const t=D(),n=Array.from({length:15},()=>`<tr class="skeleton-row">${t.map(a=>`<td><div class="skeleton-block" style="width:${a.id==="headline"?200+Math.random()*200:a.id==="summary"?100+Math.random()*100:50+Math.random()*30}px"></div></td>`).join("")}</tr>`);e.innerHTML=n.join("")}function Ue(e){const t=l("#news-body");if(!t)return;const n=D().length;t.innerHTML=`
    <tr>
      <td colspan="${n}">
        <div class="loading-state">
          <div class="loading-spinner"></div>
          <div>${p(e)}</div>
        </div>
      </td>
    </tr>`}function ye(){const e=l("#source-list");if(e){if(s.sources.length)e.innerHTML=s.sources.map(t=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${t.name}">
        <span>${t.name.replace(/_/g," ")}</span>
        <span class="source-count">${t.total_items}</span>
      </label>`).join("");else{const t=["CNBC","CNBC_World","Reuters_Business","MarketWatch","MarketWatch_Markets","Investing_com","Yahoo_Finance","Nasdaq","SeekingAlpha","Benzinga","AP_News","Bloomberg_Business","Bloomberg_Markets","BBC_Business","Google_News_Business"];e.innerHTML=t.map(n=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${n}">
        <span>${n.replace(/_/g," ")}</span>
        <span class="source-count">--</span>
      </label>`).join("")}e.querySelectorAll('input[type="checkbox"]').forEach(t=>{t.addEventListener("change",()=>{je(),T()})})}}function je(){const e=new Set,t=[];F('#source-list input[type="checkbox"]').forEach(n=>{n.checked?t.push(n.dataset.source):e.add(n.dataset.source)}),e.size===0?s.filter.sources=new Set:s.filter.sources=new Set(t)}function We(){const e=Ie(),t={all:l("#sentiment-count-all"),bullish:l("#sentiment-count-bullish"),bearish:l("#sentiment-count-bearish"),neutral:l("#sentiment-count-neutral")};Object.entries(t).forEach(([n,i])=>{i&&(i.textContent=e[n]||0)})}function ze(){const e=l("#total-items");if(e){const t=fe();e.textContent=t.length}}function Ge(){if(!s.stats)return;const e=l("#total-items");e&&s.filter.sentiment==="all"&&s.filter.sources.size===0&&!s.filter.query&&(e.textContent=s.stats.total_items);const t=l("#feed-count");t&&(t.textContent=s.stats.feed_count);const n=l("#avg-sentiment");if(n){const i=s.stats.avg_sentiment_score;n.textContent=(i>=0?"+":"")+i.toFixed(3),n.style.color=i>.05?"var(--green)":i<-.05?"var(--red)":"var(--yellow)"}}function ee(e){const t=l("#connection-dot"),n=l("#connection-label");t&&(t.className=e?"status-dot connected":"status-dot disconnected"),n&&(n.textContent=e?"LIVE":"DISCONNECTED")}function Ye(){const e=l("#last-refresh");e&&s.lastRefresh&&(e.textContent=z(s.lastRefresh));const t=l("#items-per-sec");t&&(t.textContent=s.itemsPerSecond)}function te(){const e=l("#clock");if(!e)return;const t=new Date,n=t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"}),i=t.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric",year:"numeric"});e.textContent=`${i}  ${n}`}function be(){we(),s.refreshTimer=setInterval(()=>{A()},s.refreshInterval)}function we(){s.refreshTimer&&(clearInterval(s.refreshTimer),s.refreshTimer=null)}function Xe(){F(".sentiment-filter-btn").forEach(d=>{d.addEventListener("click",()=>{const b=d.dataset.sentiment;s.filter.sentiment=b,F(".sentiment-filter-btn").forEach(k=>k.classList.remove("active")),d.classList.add("active"),T()})});const e=l("#search-input");if(e){let d;e.addEventListener("input",b=>{clearTimeout(d),d=setTimeout(()=>{s.filter.query=b.target.value.trim(),T()},150)})}const t=l("#date-from"),n=l("#date-to");t&&t.addEventListener("change",d=>{s.filter.dateFrom=d.target.value,A()}),n&&n.addEventListener("change",d=>{s.filter.dateTo=d.target.value,A()});const i=l("#btn-clear-dates");i&&i.addEventListener("click",()=>{s.filter.dateFrom="",s.filter.dateTo="",t&&(t.value=""),n&&(n.value=""),A()});const a=l("#hide-duplicates");a&&a.addEventListener("change",d=>{s.filter.hideDuplicates=d.target.checked,T()});const r=l("#btn-refresh");r&&r.addEventListener("click",Q);const o=l("#refresh-interval");o&&o.addEventListener("change",d=>{s.refreshInterval=parseInt(d.target.value,10),be()});const c=l("#btn-docs");c&&c.addEventListener("click",()=>R(!0));const u=l("#modal-close");u&&u.addEventListener("click",()=>R(!1));const f=l("#modal-overlay");f&&f.addEventListener("click",d=>{d.target===f&&R(!1)});const y=l("#btn-col-settings");y&&y.addEventListener("click",d=>{d.stopPropagation(),Z(),s.columnSettingsOpen&&Y()}),document.addEventListener("click",d=>{s._dragging||s.columnSettingsOpen&&!d.target.closest("#column-settings-wrap")&&Z(!1)});const g=l("#news-body");g&&g.addEventListener("click",d=>{if(d.target.closest("a"))return;const b=d.target.closest(".ticker-badge[data-ticker]");if(b){d.stopPropagation(),$e(b.dataset.ticker);return}const k=d.target.closest("tr[data-id]");if(!k)return;const O=k.dataset.id,B=s.items.find(X=>String(X.id)===O);B&&Ke(B)});const v=l("#detail-modal-close");v&&v.addEventListener("click",U);const w=l("#detail-modal-overlay");w&&w.addEventListener("click",d=>{d.target===w&&U()});const E=l("#company-profile-close");E&&E.addEventListener("click",j);const S=l("#company-profile-overlay");S&&S.addEventListener("click",d=>{d.target===S&&j()});const _=document.querySelectorAll(".cp-tab");_.forEach(d=>{d.addEventListener("click",()=>{const b=d.dataset.tab;b!==s.companyProfileActiveTab&&(s.companyProfileActiveTab=b,_.forEach(k=>k.classList.toggle("active",k.dataset.tab===b)),b==="fundamentals"&&s.companyProfileData?ke(s.companyProfileData):b==="financials"?Je(s.companyProfileSymbol):b==="competitors"?Qe(s.companyProfileSymbol):b==="institutions"?Ze(s.companyProfileSymbol):b==="insiders"&&et(s.companyProfileSymbol))})});const h=l("#btn-sound");h&&h.addEventListener("click",()=>{s.soundEnabled=!s.soundEnabled,h.classList.toggle("active",s.soundEnabled),h.title=s.soundEnabled?"Sound alerts ON":"Sound alerts OFF";const d=h.querySelector(".sound-icon");d&&(d.innerHTML=s.soundEnabled?'<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>':'<path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>')});const x=l("#hamburger-btn");x&&x.addEventListener("click",V);const m=l("#sidebar-backdrop");m&&m.addEventListener("click",()=>V(!1)),document.addEventListener("keydown",d=>{if(d.target.tagName==="INPUT"||d.target.tagName==="TEXTAREA"||d.target.tagName==="SELECT"){d.key==="Escape"&&d.target.blur();return}switch(d.key.toLowerCase()){case"r":d.preventDefault(),Q();break;case"f":d.preventDefault();const b=l("#search-input");b&&b.focus();break;case"1":d.preventDefault(),q("all");break;case"2":d.preventDefault(),q("bullish");break;case"3":d.preventDefault(),q("bearish");break;case"4":d.preventDefault(),q("neutral");break;case"escape":s.companyProfileOpen?j():s.detailModalOpen?U():s.modalOpen&&R(!1),s.sidebarOpen&&V(!1);break}});const $=l("#api-url");$&&$.addEventListener("click",()=>{const d=`${C}/news`;navigator.clipboard&&navigator.clipboard.writeText(d).then(()=>{$.textContent="Copied!",setTimeout(()=>{$.textContent=`${C}/news`},1500)})})}function q(e){s.filter.sentiment=e,F(".sentiment-filter-btn").forEach(t=>{t.classList.toggle("active",t.dataset.sentiment===e)}),T()}function V(e){const t=typeof e=="boolean"?e:!s.sidebarOpen;s.sidebarOpen=t;const n=l(".sidebar"),i=l("#sidebar-backdrop");n&&n.classList.toggle("open",t),i&&i.classList.toggle("open",t)}function R(e){s.modalOpen=e;const t=l("#modal-overlay");t&&t.classList.toggle("open",e),e&&F(".api-base-url").forEach(n=>{n.textContent=window.location.origin+window.location.pathname.replace(/\/[^/]*$/,"")})}function Ke(e){s.detailItem=e,s.detailModalOpen=!0;const t=l("#detail-modal-overlay");if(!t)return;const n=s.userTier==="max";let i="";if(i+=`<div class="detail-article">
    <h3 class="detail-headline">${p(e.title||"Untitled")}</h3>
    <div class="detail-meta">
      <span class="source-tag">${p(e.source||"")}</span>
      <span class="detail-time">${z(e.published)} · ${pe(e.published)}</span>
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
    </div>`;else{const r=e.confidence!=null?Math.round(e.confidence*100):"—",o=(e.risk_level||"").toLowerCase(),c=o==="low"?"green":o==="high"?"red":"yellow",u=e.tradeable?"YES":"NO",f=e.tradeable?"yes":"no",y=(e.sentiment_label||"neutral").toLowerCase(),g=e.sentiment_score!=null?(e.sentiment_score>=0?"+":"")+Number(e.sentiment_score).toFixed(2):"—";i+=`<div class="detail-ticker-header">
      <div class="detail-ticker-symbol">${p(e.target_asset)}</div>
      <span class="detail-asset-type">${p(e.asset_type||"—")}</span>
    </div>
    <div class="detail-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Sentiment</div>
        <div class="detail-metric-value">
          <span class="sentiment-badge ${y}"><span class="sentiment-dot"></span>${y}</span>
          <span class="detail-metric-sub">${g}</span>
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
    </div>`}const a=t.querySelector(".detail-modal-body");a&&(a.innerHTML=i),t.classList.add("open")}function U(){s.detailModalOpen=!1,s.detailItem=null;const e=l("#detail-modal-overlay");e&&e.classList.remove("open")}async function $e(e){s.companyProfileOpen=!0,s.companyProfileSymbol=e,s.companyProfileData=null,s.companyProfileLoading=!0,s.companyProfileActiveTab="fundamentals",s.companyProfileFinancials=null,s.companyProfileCompetitors=null,s.companyProfileInstitutions=null,s.companyProfileInsiders=null,document.querySelectorAll(".cp-tab").forEach(a=>{a.classList.toggle("active",a.dataset.tab==="fundamentals")});const t=l("#company-profile-overlay");if(!t)return;const n=l("#company-profile-title");n&&(n.textContent=`// ${e.toUpperCase()}`);const i=l("#company-profile-body");i&&(i.innerHTML=`<div class="cp-loading">
      <div class="cp-loading-row"><div class="skeleton" style="width:60%;height:24px"></div></div>
      <div class="cp-loading-row"><div class="skeleton" style="width:40%;height:16px"></div></div>
      <div class="cp-loading-row" style="margin-top:16px"><div class="skeleton" style="width:100%;height:80px"></div></div>
      <div class="cp-loading-grid">
        <div class="skeleton" style="width:100%;height:64px"></div>
        <div class="skeleton" style="width:100%;height:64px"></div>
      </div>
    </div>`),t.classList.add("open");try{const a=await L.fetch(`${C}/market/${encodeURIComponent(e)}/details`);if(!a.ok){const o=await a.json().catch(()=>({}));throw new Error(o.message||`HTTP ${a.status}`)}const r=await a.json();s.companyProfileData=r,s.companyProfileLoading=!1,ke(r)}catch(a){s.companyProfileLoading=!1,logger.warn("Error fetching company details for",e,a),i&&(i.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load company details for <strong>${p(e)}</strong></p>
        <span>${p(a.message)}</span>
      </div>`)}}function ke(e){const t=l("#company-profile-body");if(!t)return;const n=e.logo_url?`<img class="cp-logo" src="${p(e.logo_url)}" alt="${p(e.name)}" onerror="this.style.display='none'">`:"",i=e.homepage_url?`<a class="cp-homepage" href="${p(e.homepage_url)}" target="_blank" rel="noopener noreferrer">${p(e.homepage_url.replace(/^https?:\/\//,""))}</a>`:"";t.innerHTML=`
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
        <div class="detail-metric-value">${_e(e.market_cap)}</div>
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
  `}function j(){s.companyProfileOpen=!1,s.companyProfileSymbol=null,s.companyProfileData=null,s.companyProfileLoading=!1,s.companyProfileActiveTab="fundamentals",s.companyProfileFinancials=null,s.companyProfileCompetitors=null,s.companyProfileInstitutions=null,s.companyProfileInsiders=null;const e=l("#company-profile-overlay");e&&e.classList.remove("open")}async function Je(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileFinancials){se(s.companyProfileFinancials);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:60%;height:24px"></div></div>
    <div class="cp-loading-grid">
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
    </div>
    <div class="cp-loading-row" style="margin-top:16px"><div class="skeleton" style="width:100%;height:120px"></div></div>
  </div>`;try{const n=await L.fetch(`${C}/market/${encodeURIComponent(e)}/financials`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileFinancials=i,s.companyProfileActiveTab==="financials"&&se(i)}catch(n){logger.warn("Error fetching financials for",e,n),s.companyProfileActiveTab==="financials"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load financial data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function H(e){if(e==null)return"—";const t=Math.abs(e),n=e<0?"-":"";return t>=1e12?n+"$"+(t/1e12).toFixed(2)+"T":t>=1e9?n+"$"+(t/1e9).toFixed(2)+"B":t>=1e6?n+"$"+(t/1e6).toFixed(2)+"M":t>=1e3?n+"$"+(t/1e3).toFixed(2)+"K":n+"$"+t.toFixed(2)}function se(e){const t=l("#company-profile-body");if(!t)return;const n=e.financials,i=e.earnings||[],a=n&&(n.revenue!=null||n.net_income!=null||n.eps!=null),r=i.length>0&&i.some(f=>f.actual_eps!=null);if(!a&&!r){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No financial data available</p>
      <span>Financial data is not available for this ticker (e.g., ETFs, indices).</span>
    </div>`;return}const o=n&&n.fiscal_period&&n.fiscal_year?`${n.fiscal_period} ${n.fiscal_year}`:"",c=a?`
    ${o?`<div class="cp-fin-period">Latest Quarter: ${p(o)}</div>`:""}
    <div class="cp-fin-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Revenue</div>
        <div class="detail-metric-value">${H(n.revenue)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Net Income</div>
        <div class="detail-metric-value">${H(n.net_income)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">EPS</div>
        <div class="detail-metric-value">${n.eps!=null?"$"+n.eps.toFixed(2):"—"}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">P/E Ratio</div>
        <div class="detail-metric-value">${n.pe_ratio!=null?n.pe_ratio.toFixed(1)+"x":"—"}</div>
      </div>
    </div>`:"";let u="";if(r){const f=[...i].reverse(),y=Math.max(...f.map(v=>Math.abs(v.actual_eps||0)),.01);u=`
    <div class="cp-fin-chart-section">
      <div class="cp-desc-label">Earnings Per Share — Last 4 Quarters</div>
      <div class="cp-bar-chart">${f.map(v=>{const w=v.actual_eps;if(w==null)return"";const E=Math.min(Math.abs(w)/y*100,100),_=w>=0?"cp-bar-positive":"cp-bar-negative",h=`${v.fiscal_period} ${String(v.fiscal_year).slice(-2)}`,x=v.estimated_eps!=null,m=x&&w>=v.estimated_eps,$=x?m?"cp-bar-beat":"cp-bar-miss":_;return`<div class="cp-bar-col">
        <div class="cp-bar-value ${$}">$${w.toFixed(2)}</div>
        <div class="cp-bar-track">
          <div class="cp-bar-fill ${$}" style="height:${E}%"></div>
        </div>
        <div class="cp-bar-label">${p(h)}</div>
        ${x?`<div class="cp-bar-est">Est: $${v.estimated_eps.toFixed(2)}</div>`:""}
      </div>`}).join("")}</div>
      <div class="cp-bar-legend">
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-positive"></span>Positive</span>
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-negative"></span>Negative</span>
      </div>
    </div>`}t.innerHTML=c+u}async function Qe(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileCompetitors){ne(s.companyProfileCompetitors);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:50%;height:24px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
  </div>`;try{const n=await L.fetch(`${C}/market/${encodeURIComponent(e)}/competitors`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileCompetitors=i,s.companyProfileActiveTab==="competitors"&&ne(i)}catch(n){logger.warn("Error fetching competitors for",e,n),s.companyProfileActiveTab==="competitors"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load competitor data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function ne(e){const t=l("#company-profile-body");if(!t)return;const n=e.competitors||[];if(n.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No competitor data available</p>
      <span>Competitor information is not available for this ticker.</span>
    </div>`;return}const i=n.map(a=>{const r=a.change_percent!=null?a.change_percent:null,o=r!=null?r>=0?"positive":"negative":"",c=r!=null?`${r>=0?"+":""}${r.toFixed(2)}%`:"—",u=a.price!=null?`$${a.price.toFixed(2)}`:"—",f=H(a.market_cap),y=a.sector||"—";return`<tr class="cp-comp-row">
      <td class="cp-comp-ticker"><span class="cp-comp-ticker-link" data-ticker="${p(a.symbol)}">${p(a.symbol)}</span></td>
      <td class="cp-comp-name">${p(a.name)}</td>
      <td class="cp-comp-mcap">${f}</td>
      <td class="cp-comp-price">${u}</td>
      <td class="cp-comp-change ${o}">${c}</td>
      <td class="cp-comp-sector">${p(y)}</td>
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
    </div>`,t.querySelectorAll(".cp-comp-ticker-link[data-ticker]").forEach(a=>{a.addEventListener("click",()=>{$e(a.dataset.ticker)})})}const ie="inst_tooltip_dismissed";function P(e){if(e==null)return"—";const t=Math.abs(e);return t>=1e9?(t/1e9).toFixed(2)+"B":t>=1e6?(t/1e6).toFixed(2)+"M":t>=1e3?(t/1e3).toFixed(1)+"K":t.toLocaleString()}async function Ze(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileInstitutions){ae(s.companyProfileInstitutions);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:70%;height:20px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:50%;height:16px"></div></div>
    <div class="cp-loading-row" style="margin-top:12px"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
  </div>`;try{const n=await L.fetch(`${C}/market/${encodeURIComponent(e)}/institutions`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileInstitutions=i,s.companyProfileActiveTab==="institutions"&&ae(i)}catch(n){logger.warn("Error fetching institutions for",e,n),s.companyProfileActiveTab==="institutions"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load institutional data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function ae(e){const t=l("#company-profile-body");if(!t)return;const n=e.institutional_holders||[],i=e.major_position_changes||[];if(n.length===0&&i.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No institutional data available</p>
      <span>Institutional holdings data is not available for this ticker.</span>
    </div>`;return}const a=n.length>0?n[0].report_date:null,r=a?`<div class="cp-inst-date-banner">Holdings as of ${p(a)}</div>`:"",c=localStorage.getItem(ie)?"":`<div class="cp-inst-tooltip" id="cp-inst-tooltip">
    <div class="cp-inst-tooltip-text">
      <strong>About this data:</strong> 13F holdings are filed quarterly (up to 45 days after quarter end).
      13D/13G filings are filed in near-real-time when an investor crosses the 5% ownership threshold.
    </div>
    <button class="cp-inst-tooltip-dismiss" id="cp-inst-tooltip-dismiss">✕</button>
  </div>`;let u=0,f=0;n.forEach(m=>{m.value!=null&&(u+=m.value),m.shares_held!=null&&(f+=m.shares_held)});const y=`<div class="cp-inst-summary">
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Institutions Reporting</span>
      <span class="cp-inst-summary-value">${n.length}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Institutional Value</span>
      <span class="cp-inst-summary-value">${H(u)}</span>
    </div>
    <div class="cp-inst-summary-item">
      <span class="cp-inst-summary-label">Total Shares Held</span>
      <span class="cp-inst-summary-value">${P(f)}</span>
    </div>
  </div>`,g=n.map(m=>{const $=P(m.shares_held),d=H(m.value),b=m.change_type||"held";let k="";return b==="new"?k='<span class="cp-inst-badge cp-inst-badge-new">NEW</span>':b==="increased"?k='<span class="cp-inst-change-up">▲</span>':b==="decreased"?k='<span class="cp-inst-change-down">▼</span>':k='<span class="cp-inst-change-flat">—</span>',`<tr class="cp-inst-row">
      <td class="cp-inst-name">${p(m.institution_name||"Unknown")}</td>
      <td class="cp-inst-shares">${$}</td>
      <td class="cp-inst-value">${d}</td>
      <td class="cp-inst-change">${k}</td>
    </tr>`}).join(""),v=n.length>0?`
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
        <tbody>${g}</tbody>
      </table>
    </div>`:"",w=Date.now(),E=720*60*60*1e3,S=i.map(m=>{const $=m.filing_date||"",b=$&&w-new Date($).getTime()<E?'<span class="cp-inst-badge cp-inst-badge-new">NEW</span> ':"",k=m.percent_owned!=null?m.percent_owned.toFixed(2)+"%":"—",O=m.filing_type||"";return`<tr class="cp-inst-row ${O.includes("13D")?"cp-inst-13d":"cp-inst-13g"}">
      <td class="cp-inst-filer">${b}${p(m.filer_name||"Unknown")}</td>
      <td class="cp-inst-pct">${k}</td>
      <td class="cp-inst-filing-date">${p($)}</td>
      <td class="cp-inst-filing-type">${p(O)}</td>
    </tr>`}).join(""),_=i.length>0?`
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
        <tbody>${S}</tbody>
      </table>
    </div>`:"",h='<div class="cp-inst-source">Source: SEC EDGAR (13F quarterly + 13D/13G real-time filings)</div>';t.innerHTML=r+c+y+v+_+h;const x=document.getElementById("cp-inst-tooltip-dismiss");x&&x.addEventListener("click",()=>{localStorage.setItem(ie,"1");const m=document.getElementById("cp-inst-tooltip");m&&m.remove()})}async function et(e){if(!e)return;const t=l("#company-profile-body");if(t){if(s.companyProfileInsiders){oe(s.companyProfileInsiders);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:70%;height:20px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:50%;height:16px"></div></div>
    <div class="cp-loading-row" style="margin-top:12px"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
  </div>`;try{const n=await L.fetch(`${C}/market/${encodeURIComponent(e)}/insiders`);if(!n.ok){const a=await n.json().catch(()=>({}));throw new Error(a.message||`HTTP ${n.status}`)}const i=await n.json();s.companyProfileInsiders=i,s.companyProfileActiveTab==="insiders"&&oe(i)}catch(n){logger.warn("Error fetching insiders for",e,n),s.companyProfileActiveTab==="insiders"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load insider trading data for <strong>${p(e)}</strong></p>
        <span>${p(n.message)}</span>
      </div>`)}}}function oe(e){const t=l("#company-profile-body");if(!t)return;const n=e.insider_transactions||[];if(n.length===0){t.innerHTML=`<div class="cp-error">
      <div class="cp-error-icon">—</div>
      <p>No insider transaction data available for <strong>${p(e.symbol||"")}</strong></p>
    </div>`;return}const i=Date.now()-2160*60*60*1e3;let a=0,r=0,o=0,c=0;for(const h of n){if((h.filing_date?new Date(h.filing_date).getTime():0)<i)continue;const m=(h.transaction_type||"").toLowerCase(),$=Math.abs(h.total_value||0);m==="purchase"?(a+=$,o++):m==="sale"&&(r+=$,c++)}const u=a-r,f=u>0?"cp-insider-sentiment-buy":u<0?"cp-insider-sentiment-sell":"cp-insider-sentiment-neutral",y=u>0?"Net Buying":u<0?"Net Selling":"Neutral",g=u>0?"▲":u<0?"▼":"●",v=`<div class="cp-insider-sentiment ${f}">
    <div class="cp-insider-sentiment-header">
      <span class="cp-insider-sentiment-icon">${g}</span>
      <span class="cp-insider-sentiment-label">${y}</span>
      <span class="cp-insider-sentiment-period">90-day insider activity</span>
    </div>
    <div class="cp-insider-sentiment-stats">
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-buy-text">${o} buys</span>
        <span class="cp-insider-stat-amount">$${P(a)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value cp-insider-sell-text">${c} sells</span>
        <span class="cp-insider-stat-amount">$${P(r)}</span>
      </div>
      <div class="cp-insider-stat">
        <span class="cp-insider-stat-value">Net</span>
        <span class="cp-insider-stat-amount ${f}">${u>=0?"+":""}$${P(Math.abs(u))}</span>
      </div>
    </div>
  </div>`,S=`<div class="cp-insider-table-wrap">
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
      <tbody>${[...n].sort((h,x)=>{const m=h.filing_date||"";return(x.filing_date||"").localeCompare(m)}).map(h=>{const x=(h.transaction_type||"").toLowerCase();let m="cp-insider-row-other";x==="purchase"?m="cp-insider-row-buy":x==="sale"?m="cp-insider-row-sell":x==="option exercise"&&(m="cp-insider-row-exercise");const $=h.shares!=null?P(h.shares):"—",d=h.price_per_share!=null?"$"+h.price_per_share.toFixed(2):"—",b=h.total_value!=null?"$"+P(h.total_value):"—",k=h.shares_held_after!=null?P(h.shares_held_after):"—";return`<tr class="cp-insider-row ${m}">
      <td class="cp-insider-date">${p(h.filing_date||"")}</td>
      <td class="cp-insider-name">${p(h.insider_name||"Unknown")}</td>
      <td class="cp-insider-title">${p(h.title||"")}</td>
      <td class="cp-insider-type">${p(h.transaction_type||"")}</td>
      <td class="cp-insider-shares">${$}</td>
      <td class="cp-insider-price">${d}</td>
      <td class="cp-insider-total">${b}</td>
      <td class="cp-insider-holdings">${k}</td>
    </tr>`}).join("")}</tbody>
    </table>
  </div>`,_='<div class="cp-insider-source">Source: SEC EDGAR Form 4 (filed within 2 business days of transaction)</div>';t.innerHTML=v+S+_}function tt(){if(typeof L>"u")return;L.init();const e=l("#btn-signin");e&&e.addEventListener("click",()=>{L.showAuthModal("signin")});const t=l("#btn-signout");t&&t.addEventListener("click",()=>{L.signOut()});const n=l("#btn-user"),i=l("#user-dropdown");n&&i&&(n.addEventListener("click",a=>{a.stopPropagation(),i.classList.toggle("open")}),document.addEventListener("click",()=>{i.classList.remove("open")})),L.onAuthChange(a=>{st(a)})}function st(e){const t=l("#btn-signin"),n=l("#user-menu");if(e){t&&(t.style.display="none"),n&&(n.style.display="flex");const i=l("#user-avatar"),a=l("#user-name"),r=l("#dropdown-email");i&&e.photoURL&&(i.src=e.photoURL,i.alt=e.displayName||""),a&&(a.textContent=e.displayName||e.email||""),r&&(r.textContent=e.email||""),nt()}else t&&(t.style.display="flex"),n&&(n.style.display="none"),xe()}async function nt(){try{const e=await L.fetch(`${C}/auth/tier`);if(!e.ok)return;const t=await e.json(),n=t.tier||"free",i=n==="plus"?"pro":n,a=t.features||{};s.userTier=i,s.userFeatures=a,Y(),I(),T(),G(),Pe();const r=l("#tier-badge"),o=l("#dropdown-tier");if(r&&(r.textContent=i.toUpperCase(),r.className="tier-badge"+(i!=="free"?" "+i:"")),o){const c={free:"Free Plan",pro:"Pro Plan",plus:"Pro Plan"};o.textContent=c[i]||"Free Plan"}a.terminal_access===!1||i==="free"?xe():it()}catch{}}function xe(){if(l("#upgrade-gate"))return;const e=document.createElement("div");e.id="upgrade-gate",e.style.cssText="position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(1,4,9,0.95);",e.innerHTML='<div style="text-align:center;max-width:420px;padding:40px;border:1px solid rgba(48,54,61,0.8);border-radius:12px;background:#0d1117;"><h2 style="color:#e6edf3;margin:0 0 12px;font-size:22px;">Upgrade to Pro</h2><p style="color:#8b949e;margin:0 0 24px;line-height:1.6;">The SIGNAL terminal requires a Pro subscription. Get full access to real-time news, sentiment analysis, and deduplication.</p><a href="/pricing" style="display:inline-block;padding:10px 28px;background:#238636;color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">View Plans</a><div style="margin-top:16px;"><a href="/" style="color:#8b949e;font-size:13px;text-decoration:underline;">Back to home</a></div></div>',document.body.appendChild(e),we(),ue()}function it(){const e=l("#upgrade-gate");e&&e.remove()}function re(){Ae(),He(),De(),I(),Ve(),ye(),Xe(),te(),tt(),setInterval(te,1e3),A(),W(),J(),be(),setInterval(()=>{W(),J()},3e4)}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",re):re();document.addEventListener("DOMContentLoaded",function(){var e=document.getElementById("auth-gate"),t=document.getElementById("auth-gate-signin");function n(){typeof SignalAuth<"u"&&SignalAuth.isSignedIn()?e.classList.add("hidden"):e.classList.remove("hidden")}t&&t.addEventListener("click",function(){typeof SignalAuth<"u"&&SignalAuth.showAuthModal("signin")}),typeof SignalAuth<"u"&&SignalAuth.onAuthChange(n),setTimeout(function(){typeof SignalAuth<"u"&&(SignalAuth.onAuthChange(n),n())},500)});

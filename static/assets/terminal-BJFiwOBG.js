import{S as b}from"./auth-C4Y_TkCR.js";/* empty css             *//* empty css                 */const k="/api",we=200,ke=6e4,Le=1e4,X=10,L=[{id:"time",label:"Time",defaultVisible:!0,required:!1,requiredFeature:null},{id:"sentiment",label:"Sentiment",defaultVisible:!0,required:!1,requiredFeature:"sentiment_filter"},{id:"source",label:"Source",defaultVisible:!0,required:!1,requiredFeature:null},{id:"headline",label:"Headline",defaultVisible:!0,required:!0,requiredFeature:null},{id:"summary",label:"Summary",defaultVisible:!0,required:!1,requiredFeature:null},{id:"ticker",label:"Ticker",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"confidence",label:"Confidence",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"risk",label:"Risk Level",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"},{id:"tradeable",label:"Tradeable",defaultVisible:!1,required:!1,requiredFeature:"ai_ticker_recommendations"}],ne="instnews_column_visibility",se="instnews_column_order",ie="instnews_column_widths",D=60;let n={items:[],seenIds:new Set,newIds:new Set,sources:[],stats:null,filter:{sentiment:"all",sources:new Set,query:"",dateFrom:"",dateTo:"",hideDuplicates:!1},refreshInterval:5e3,refreshTimer:null,lastRefresh:null,connected:!1,loading:!0,totalFetched:0,fetchCount:0,itemsPerSecond:0,startTime:Date.now(),sidebarOpen:!1,modalOpen:!1,detailModalOpen:!1,detailItem:null,userTier:null,userFeatures:{},soundEnabled:!1,columnVisibility:{},columnOrder:L.map(e=>e.id),columnWidths:{},columnSettingsOpen:!1,marketPrices:{},priceRefreshTimer:null,companyProfileOpen:!1,companyProfileSymbol:null,companyProfileData:null,companyProfileLoading:!1,companyProfileActiveTab:"fundamentals",companyProfileFinancials:null,companyProfileCompetitors:null};const o=e=>document.querySelector(e),M=e=>[...document.querySelectorAll(e)];function V(e){if(!e)return"--:--:--";try{const t=new Date(e);return isNaN(t.getTime())?"--:--:--":t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"})}catch{return"--:--:--"}}function ae(e){if(!e)return"";try{const t=new Date(e),i=new Date-t;return i<0?"just now":i<6e4?`${Math.floor(i/1e3)}s ago`:i<36e5?`${Math.floor(i/6e4)}m ago`:i<864e5?`${Math.floor(i/36e5)}h ago`:`${Math.floor(i/864e5)}d ago`}catch{return""}}function $e(e){if(!e)return!1;try{const t=new Date(e);return Date.now()-t.getTime()<ke}catch{return!1}}function u(e){const t=document.createElement("div");return t.textContent=e,t.innerHTML}function xe(e,t){return e?e.length>t?e.slice(0,t)+"…":e:""}function Ee(e){return e==null?"—":e>=1e12?"$"+(e/1e12).toFixed(2)+"T":e>=1e9?"$"+(e/1e9).toFixed(2)+"B":e>=1e6?"$"+(e/1e6).toFixed(2)+"M":"$"+e.toLocaleString()}async function _(){try{const e=new URLSearchParams({limit:we});n.filter.dateFrom&&e.set("from",n.filter.dateFrom),n.filter.dateTo&&e.set("to",n.filter.dateTo);const t=await b.fetch(`${k}/news?${e}`);if(!t.ok)throw new Error(`HTTP ${t.status}`);const s=await t.json();if(n.connected=!0,n.loading=!1,n.fetchCount++,n.lastRefresh=new Date().toISOString(),s.items&&s.items.length>0){const i=new Set;for(const l of s.items)n.seenIds.has(l.id)||(i.add(l.id),n.seenIds.add(l.id));n.soundEnabled&&i.size>0&&n.fetchCount>1&&Se(),n.newIds=i,n.items=s.items,n.totalFetched=s.count;const a=(Date.now()-n.startTime)/1e3;n.itemsPerSecond=a>0?(n.totalFetched/a).toFixed(1):0}w(),je(),K(!0),j()}catch{n.connected=!1,n.loading=!1,K(!1),n.items.length===0&&Re("Unable to connect to API. Retrying...")}}async function Y(){try{const e=await b.fetch(`${k}/sources`);if(!e.ok)return;const t=await e.json();n.sources=t.sources||[],fe()}catch{}}async function B(){try{const e=await b.fetch(`${k}/stats`);if(!e.ok)return;n.stats=await e.json(),Ve()}catch{}}async function j(){if(!n.userFeatures.ai_ticker_recommendations||!n.columnVisibility.ticker)return;const e=[...new Set(n.items.map(t=>t.target_asset).filter(Boolean))];if(e.length!==0){for(let t=0;t<e.length;t+=X){const i=e.slice(t,t+X).map(async a=>{try{const l=await b.fetch(`${k}/market/${encodeURIComponent(a)}`);l.ok&&(n.marketPrices[a]=await l.json())}catch{}});await Promise.all(i)}w()}}function Ce(){re(),n.userFeatures.ai_ticker_recommendations&&n.columnVisibility.ticker&&(n.priceRefreshTimer=setInterval(j,Le))}function re(){n.priceRefreshTimer&&(clearInterval(n.priceRefreshTimer),n.priceRefreshTimer=null)}async function G(){try{const e=o("#btn-refresh");e&&(e.disabled=!0,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>Refreshing'),await b.fetch(`${k}/refresh`,{method:"POST"}),await _(),await B(),e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}catch{const e=o("#btn-refresh");e&&(e.disabled=!1,e.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh')}}function Se(){try{const e=new(window.AudioContext||window.webkitAudioContext),t=e.createOscillator(),s=e.createGain();t.connect(s),s.connect(e.destination),t.type="sine",t.frequency.setValueAtTime(880,e.currentTime),t.frequency.setValueAtTime(1100,e.currentTime+.05),s.gain.setValueAtTime(.08,e.currentTime),s.gain.exponentialRampToValueAtTime(.001,e.currentTime+.15),t.start(e.currentTime),t.stop(e.currentTime+.15)}catch{}}function oe(){return n.items.filter(e=>{if(n.filter.sentiment!=="all"&&e.sentiment_label!==n.filter.sentiment||n.filter.sources.size>0&&!n.filter.sources.has(e.source))return!1;if(n.filter.query){const t=n.filter.query.toLowerCase(),s=(e.title||"").toLowerCase().includes(t),i=(e.summary||"").toLowerCase().includes(t);if(!s&&!i)return!1}return!(n.filter.hideDuplicates&&e.duplicate)})}function Te(){const e={all:0,bullish:0,bearish:0,neutral:0};for(const t of n.items)e.all++,e[t.sentiment_label]!==void 0&&e[t.sentiment_label]++;return e}function _e(){try{const t=localStorage.getItem(ne);if(t){const s=JSON.parse(t),i={};for(const a of L)i[a.id]=a.id in s?s[a.id]:a.defaultVisible;n.columnVisibility=i;return}}catch{}const e={};for(const t of L)e[t.id]=t.defaultVisible;n.columnVisibility=e}function Me(){try{localStorage.setItem(ne,JSON.stringify(n.columnVisibility))}catch{}}function Pe(){try{const e=localStorage.getItem(se);if(e){const t=JSON.parse(e);if(Array.isArray(t)){const s=new Set(L.map(a=>a.id)),i=t.filter(a=>s.has(a));for(const a of L)i.includes(a.id)||i.push(a.id);n.columnOrder=i;return}}}catch{}n.columnOrder=L.map(e=>e.id)}function le(){try{localStorage.setItem(se,JSON.stringify(n.columnOrder))}catch{}}function Ae(){try{const e=localStorage.getItem(ie);if(e){const t=JSON.parse(e);if(t&&typeof t=="object"){const s={};for(const i of L)i.id in t&&typeof t[i.id]=="number"&&t[i.id]>=D&&(s[i.id]=t[i.id]);n.columnWidths=s;return}}}catch{}n.columnWidths={}}function ce(){try{localStorage.setItem(ie,JSON.stringify(n.columnWidths))}catch{}}function de(){const e={};for(const t of L)e[t.id]=t;return n.columnOrder.map(t=>e[t]).filter(Boolean)}function ue(e){return!e.requiredFeature||n.userTier===null?!1:!n.userFeatures[e.requiredFeature]}function P(){return de().filter(e=>ue(e)?!1:n.columnVisibility[e.id]!==!1)}function S(){const e=document.querySelector(".news-table thead");if(!e)return;const t=P();e.innerHTML="<tr>"+t.map(i=>{const a=n.columnWidths[i.id],l=a?` style="width:${a}px"`:"";return`<th class="col-${i.id}" draggable="true" data-col-id="${i.id}"${l}><span class="th-drag-label">${i.label}</span><span class="col-resize-handle" data-col-id="${i.id}"></span></th>`}).join("")+"</tr>";const s=document.querySelector(".news-table");s&&(s.style.tableLayout=Object.keys(n.columnWidths).length>0?"fixed":""),Fe(),Ie()}function Ie(){const e=document.querySelector(".news-table thead tr");if(!e)return;const t=e.querySelectorAll("th[draggable]");let s=null;t.forEach(i=>{i.addEventListener("dragstart",a=>{if(a.target.closest(".col-resize-handle")){a.preventDefault();return}s=i,i.classList.add("th-dragging"),a.dataTransfer.effectAllowed="move",a.dataTransfer.setData("text/plain",i.dataset.colId)}),i.addEventListener("dragover",a=>{if(a.preventDefault(),a.dataTransfer.dropEffect="move",!s||i===s)return;e.querySelectorAll("th").forEach(c=>c.classList.remove("th-drag-over-left","th-drag-over-right"));const l=i.getBoundingClientRect(),r=l.left+l.width/2;a.clientX<r?i.classList.add("th-drag-over-left"):i.classList.add("th-drag-over-right")}),i.addEventListener("dragleave",()=>{i.classList.remove("th-drag-over-left","th-drag-over-right")}),i.addEventListener("drop",a=>{if(a.preventDefault(),a.stopPropagation(),!s||i===s)return;e.querySelectorAll("th").forEach(g=>g.classList.remove("th-drag-over-left","th-drag-over-right"));const l=s.dataset.colId,r=i.dataset.colId,c=[...n.columnOrder],f=c.indexOf(l),p=c.indexOf(r);if(f===-1||p===-1)return;c.splice(f,1);const h=i.getBoundingClientRect(),v=h.left+h.width/2,m=a.clientX<v?c.indexOf(r):c.indexOf(r)+1;c.splice(m,0,l),n.columnOrder=c,le(),S(),w(),n.columnSettingsOpen&&W()}),i.addEventListener("dragend",()=>{i.classList.remove("th-dragging"),e.querySelectorAll("th").forEach(a=>a.classList.remove("th-drag-over-left","th-drag-over-right"))})})}function Fe(){document.querySelectorAll(".col-resize-handle").forEach(t=>{t.addEventListener("mousedown",Oe),t.addEventListener("dblclick",qe)})}function Oe(e){e.preventDefault(),e.stopPropagation();const t=e.target,s=t.parentElement,i=t.dataset.colId,a=e.clientX,l=s.offsetWidth,r=document.querySelector(".news-table");r&&(r.style.tableLayout="fixed");const c=[...document.querySelectorAll(".news-table thead th")];let f=0;c.forEach(v=>{const m=v.offsetWidth;v.style.width=m+"px",f+=m}),r&&(r.style.width=f+"px"),document.body.style.cursor="col-resize",document.body.style.userSelect="none",t.classList.add("active");function p(v){const m=v.clientX-a,g=Math.max(D,l+m);s.style.width=g+"px",r&&(r.style.width=f+(g-l)+"px")}function h(v){document.removeEventListener("mousemove",p),document.removeEventListener("mouseup",h),document.body.style.cursor="",document.body.style.userSelect="",t.classList.remove("active"),c.forEach(g=>{const $=g.dataset.colId;$&&(n.columnWidths[$]=g.offsetWidth)});const m=v.clientX-a;n.columnWidths[i]=Math.max(D,l+m),r&&(r.style.width=""),ce(),S(),w()}document.addEventListener("mousemove",p),document.addEventListener("mouseup",h)}function qe(e){e.preventDefault(),e.stopPropagation();const t=e.target.dataset.colId,i=P().findIndex(p=>p.id===t);if(i===-1)return;const a=document.querySelectorAll("#news-body tr");let l=D;const r=e.target.parentElement,c=document.createElement("span");c.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;",c.textContent=r.textContent,document.body.appendChild(c),l=Math.max(l,c.offsetWidth+32),document.body.removeChild(c),a.forEach(p=>{if(p.classList.contains("skeleton-row"))return;const v=p.querySelectorAll("td")[i];if(!v)return;const m=document.createElement("div");m.style.cssText="visibility:hidden;position:absolute;white-space:nowrap;font-size:12px;",m.innerHTML=v.innerHTML,document.body.appendChild(m),l=Math.max(l,m.offsetWidth+24),document.body.removeChild(m)}),l=Math.min(l,600);const f=document.querySelector(".news-table");f&&(f.style.tableLayout="fixed"),n.columnWidths[t]=l,ce(),S(),w()}function De(e,t,s,i){switch(e){case"time":return`<td class="cell-time" title="${ae(t.published)}">${V(t.published)}</td>`;case"sentiment":return`<td class="cell-sentiment"><span class="sentiment-badge ${t.sentiment_label}"><span class="sentiment-dot"></span>${t.sentiment_label}</span></td>`;case"source":return`<td class="cell-source"><span class="source-tag">${u(t.source||"")}</span></td>`;case"headline":return`<td class="cell-headline"><a href="${u(t.link||"#")}" target="_blank" rel="noopener noreferrer">${u(t.title||"Untitled")}</a>${s?'<span class="badge-new">NEW</span>':""}${i}</td>`;case"summary":return`<td class="cell-summary">${u(xe(t.summary,120))}</td>`;case"ticker":{if(!t.target_asset)return'<td class="cell-ticker"><span class="cell-dash">—</span></td>';const a=u(t.target_asset),l=n.marketPrices[t.target_asset];let r="";if(l&&l.price!=null){const c=l.change_percent||0,f=c>=0?"+":"";r=`<span class="ticker-price ${c>0?"price-up":c<0?"price-down":"price-flat"}">$${l.price.toFixed(2)} <span class="ticker-change">${f}${c.toFixed(2)}%</span></span>`}return`<td class="cell-ticker"><span class="ticker-badge" data-ticker="${a}">${a}${r}</span></td>`}case"confidence":return`<td class="cell-confidence">${t.confidence!=null?Math.round(t.confidence*100)+"%":'<span class="cell-dash">—</span>'}</td>`;case"risk":{if(!t.risk_level)return'<td class="cell-risk"><span class="cell-dash">—</span></td>';const a=t.risk_level.toLowerCase();return`<td class="cell-risk"><span class="risk-badge ${a==="low"?"green":a==="high"?"red":"yellow"}">${u(t.risk_level.toUpperCase())}</span></td>`}case"tradeable":return t.tradeable==null?'<td class="cell-tradeable"><span class="cell-dash">—</span></td>':`<td class="cell-tradeable"><span class="tradeable-badge ${t.tradeable?"yes":"no"}">${t.tradeable?"YES":"NO"}</span></td>`;default:return"<td></td>"}}function J(e){const t=typeof e=="boolean"?e:!n.columnSettingsOpen;n.columnSettingsOpen=t;const s=o("#column-settings-panel");s&&s.classList.toggle("open",t)}function W(){const e=o("#column-settings-panel");if(!e)return;const s=de().map(r=>{const c=ue(r),f=!c&&n.columnVisibility[r.id]!==!1,p=r.required||c;return`<div class="col-toggle-item${c?" locked":""}${r.required?" required":""}" draggable="true" data-col-id="${r.id}">
      <span class="col-drag-handle" aria-label="Drag to reorder">≡</span>
      <span class="col-toggle-label">
        ${c?'<svg class="col-lock-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>':""}
        ${u(r.label)}
      </span>
      <label class="col-toggle-switch${p?" disabled":""}">
        <input type="checkbox" ${f?"checked":""} ${p?"disabled":""} data-col-id="${r.id}">
        <span class="col-toggle-track"><span class="col-toggle-thumb"></span></span>
      </label>
    </div>`});e.innerHTML=`<div class="col-settings-header"><span>Columns</span></div>
    <div class="col-settings-list">${s.join("")}</div>`,e.querySelectorAll('input[type="checkbox"]').forEach(r=>{r.addEventListener("change",c=>{const f=c.target.dataset.colId;n.columnVisibility[f]=c.target.checked,Me(),S(),w()})});const i=e.querySelector(".col-settings-list");let a=null,l=!1;i.querySelectorAll(".col-drag-handle").forEach(r=>{r.addEventListener("mousedown",()=>{l=!0})}),document.addEventListener("mouseup",()=>{l=!1},{once:!1}),i.querySelectorAll(".col-toggle-item[draggable]").forEach(r=>{r.addEventListener("dragstart",c=>{if(!l){c.preventDefault();return}a=r,n._dragging=!0,r.classList.add("dragging"),c.dataTransfer.effectAllowed="move",c.dataTransfer.setData("text/plain",r.dataset.colId)}),r.addEventListener("dragover",c=>{if(c.preventDefault(),c.dataTransfer.dropEffect="move",!a||r===a)return;i.querySelectorAll(".col-toggle-item").forEach(h=>h.classList.remove("drag-over-above","drag-over-below"));const f=r.getBoundingClientRect(),p=f.top+f.height/2;c.clientY<p?r.classList.add("drag-over-above"):r.classList.add("drag-over-below")}),r.addEventListener("dragleave",()=>{r.classList.remove("drag-over-above","drag-over-below")}),r.addEventListener("drop",c=>{if(c.preventDefault(),c.stopPropagation(),!a||r===a)return;i.querySelectorAll(".col-toggle-item").forEach(v=>v.classList.remove("drag-over-above","drag-over-below"));const f=r.getBoundingClientRect(),p=f.top+f.height/2;c.clientY<p?i.insertBefore(a,r):i.insertBefore(a,r.nextSibling);const h=[...i.querySelectorAll(".col-toggle-item[data-col-id]")].map(v=>v.dataset.colId);n.columnOrder=h,le(),S(),w()}),r.addEventListener("dragend",()=>{r.classList.remove("dragging"),n._dragging=!1,i.querySelectorAll(".col-toggle-item").forEach(c=>c.classList.remove("drag-over-above","drag-over-below"))})}),i.addEventListener("dragover",r=>{r.preventDefault()})}function w(){const e=o("#news-body");if(!e)return;const t=oe(),s=P(),i=s.length;if(t.length===0&&!n.loading){e.innerHTML=`
      <tr>
        <td colspan="${i}">
          <div class="empty-state">
            <div class="icon">◇</div>
            <div>No items match current filters</div>
            <div style="font-size:11px">Try adjusting sentiment or source filters</div>
          </div>
        </td>
      </tr>`;return}const a=t.map(l=>{const r=n.newIds.has(l.id),c=$e(l.fetched_at),f=r?"news-row-new":"",p=l.duplicate?'<span class="badge-dup">DUP</span>':"",h=s.map(v=>De(v.id,l,c,p)).join("");return`<tr class="${f}" data-id="${l.id}">${h}</tr>`});e.innerHTML=a.join(""),Be(),Ue()}function He(){const e=o("#news-body");if(!e)return;const t=P(),s=Array.from({length:15},()=>`<tr class="skeleton-row">${t.map(a=>`<td><div class="skeleton-block" style="width:${a.id==="headline"?200+Math.random()*200:a.id==="summary"?100+Math.random()*100:50+Math.random()*30}px"></div></td>`).join("")}</tr>`);e.innerHTML=s.join("")}function Re(e){const t=o("#news-body");if(!t)return;const s=P().length;t.innerHTML=`
    <tr>
      <td colspan="${s}">
        <div class="loading-state">
          <div class="loading-spinner"></div>
          <div>${u(e)}</div>
        </div>
      </td>
    </tr>`}function fe(){const e=o("#source-list");if(e){if(n.sources.length)e.innerHTML=n.sources.map(t=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${t.name}">
        <span>${t.name.replace(/_/g," ")}</span>
        <span class="source-count">${t.total_items}</span>
      </label>`).join("");else{const t=["CNBC","CNBC_World","Reuters_Business","MarketWatch","MarketWatch_Markets","Investing_com","Yahoo_Finance","Nasdaq","SeekingAlpha","Benzinga","AP_News","Bloomberg_Business","Bloomberg_Markets","BBC_Business","Google_News_Business"];e.innerHTML=t.map(s=>`
      <label class="source-item">
        <input type="checkbox" checked data-source="${s}">
        <span>${s.replace(/_/g," ")}</span>
        <span class="source-count">--</span>
      </label>`).join("")}e.querySelectorAll('input[type="checkbox"]').forEach(t=>{t.addEventListener("change",()=>{Ne(),w()})})}}function Ne(){const e=new Set,t=[];M('#source-list input[type="checkbox"]').forEach(s=>{s.checked?t.push(s.dataset.source):e.add(s.dataset.source)}),e.size===0?n.filter.sources=new Set:n.filter.sources=new Set(t)}function Be(){const e=Te(),t={all:o("#sentiment-count-all"),bullish:o("#sentiment-count-bullish"),bearish:o("#sentiment-count-bearish"),neutral:o("#sentiment-count-neutral")};Object.entries(t).forEach(([s,i])=>{i&&(i.textContent=e[s]||0)})}function Ue(){const e=o("#total-items");if(e){const t=oe();e.textContent=t.length}}function Ve(){if(!n.stats)return;const e=o("#total-items");e&&n.filter.sentiment==="all"&&n.filter.sources.size===0&&!n.filter.query&&(e.textContent=n.stats.total_items);const t=o("#feed-count");t&&(t.textContent=n.stats.feed_count);const s=o("#avg-sentiment");if(s){const i=n.stats.avg_sentiment_score;s.textContent=(i>=0?"+":"")+i.toFixed(3),s.style.color=i>.05?"var(--green)":i<-.05?"var(--red)":"var(--yellow)"}}function K(e){const t=o("#connection-dot"),s=o("#connection-label");t&&(t.className=e?"status-dot connected":"status-dot disconnected"),s&&(s.textContent=e?"LIVE":"DISCONNECTED")}function je(){const e=o("#last-refresh");e&&n.lastRefresh&&(e.textContent=V(n.lastRefresh));const t=o("#items-per-sec");t&&(t.textContent=n.itemsPerSecond)}function Q(){const e=o("#clock");if(!e)return;const t=new Date,s=t.toLocaleTimeString("en-US",{hour12:!1,hour:"2-digit",minute:"2-digit",second:"2-digit"}),i=t.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric",year:"numeric"});e.textContent=`${i}  ${s}`}function pe(){me(),n.refreshTimer=setInterval(()=>{_()},n.refreshInterval)}function me(){n.refreshTimer&&(clearInterval(n.refreshTimer),n.refreshTimer=null)}function We(){M(".sentiment-filter-btn").forEach(d=>{d.addEventListener("click",()=>{const y=d.dataset.sentiment;n.filter.sentiment=y,M(".sentiment-filter-btn").forEach(C=>C.classList.remove("active")),d.classList.add("active"),w()})});const e=o("#search-input");if(e){let d;e.addEventListener("input",y=>{clearTimeout(d),d=setTimeout(()=>{n.filter.query=y.target.value.trim(),w()},150)})}const t=o("#date-from"),s=o("#date-to");t&&t.addEventListener("change",d=>{n.filter.dateFrom=d.target.value,_()}),s&&s.addEventListener("change",d=>{n.filter.dateTo=d.target.value,_()});const i=o("#btn-clear-dates");i&&i.addEventListener("click",()=>{n.filter.dateFrom="",n.filter.dateTo="",t&&(t.value=""),s&&(s.value=""),_()});const a=o("#hide-duplicates");a&&a.addEventListener("change",d=>{n.filter.hideDuplicates=d.target.checked,w()});const l=o("#btn-refresh");l&&l.addEventListener("click",G);const r=o("#refresh-interval");r&&r.addEventListener("change",d=>{n.refreshInterval=parseInt(d.target.value,10),pe()});const c=o("#btn-docs");c&&c.addEventListener("click",()=>q(!0));const f=o("#modal-close");f&&f.addEventListener("click",()=>q(!1));const p=o("#modal-overlay");p&&p.addEventListener("click",d=>{d.target===p&&q(!1)});const h=o("#btn-col-settings");h&&h.addEventListener("click",d=>{d.stopPropagation(),J(),n.columnSettingsOpen&&W()}),document.addEventListener("click",d=>{n._dragging||n.columnSettingsOpen&&!d.target.closest("#column-settings-wrap")&&J(!1)});const v=o("#news-body");v&&v.addEventListener("click",d=>{if(d.target.closest("a"))return;const y=d.target.closest(".ticker-badge[data-ticker]");if(y){d.stopPropagation(),ve(y.dataset.ticker);return}const C=d.target.closest("tr[data-id]");if(!C)return;const ye=C.dataset.id,z=n.items.find(be=>String(be.id)===ye);z&&ze(z)});const m=o("#detail-modal-close");m&&m.addEventListener("click",R);const g=o("#detail-modal-overlay");g&&g.addEventListener("click",d=>{d.target===g&&R()});const $=o("#company-profile-close");$&&$.addEventListener("click",N);const A=o("#company-profile-overlay");A&&A.addEventListener("click",d=>{d.target===A&&N()});const I=document.querySelectorAll(".cp-tab");I.forEach(d=>{d.addEventListener("click",()=>{const y=d.dataset.tab;y!==n.companyProfileActiveTab&&(n.companyProfileActiveTab=y,I.forEach(C=>C.classList.toggle("active",C.dataset.tab===y)),y==="fundamentals"&&n.companyProfileData?he(n.companyProfileData):y==="financials"?Xe(n.companyProfileSymbol):y==="competitors"&&Ye(n.companyProfileSymbol))})});const x=o("#btn-sound");x&&x.addEventListener("click",()=>{n.soundEnabled=!n.soundEnabled,x.classList.toggle("active",n.soundEnabled),x.title=n.soundEnabled?"Sound alerts ON":"Sound alerts OFF";const d=x.querySelector(".sound-icon");d&&(d.innerHTML=n.soundEnabled?'<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>':'<path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>')});const T=o("#hamburger-btn");T&&T.addEventListener("click",H);const F=o("#sidebar-backdrop");F&&F.addEventListener("click",()=>H(!1)),document.addEventListener("keydown",d=>{if(d.target.tagName==="INPUT"||d.target.tagName==="TEXTAREA"||d.target.tagName==="SELECT"){d.key==="Escape"&&d.target.blur();return}switch(d.key.toLowerCase()){case"r":d.preventDefault(),G();break;case"f":d.preventDefault();const y=o("#search-input");y&&y.focus();break;case"1":d.preventDefault(),O("all");break;case"2":d.preventDefault(),O("bullish");break;case"3":d.preventDefault(),O("bearish");break;case"4":d.preventDefault(),O("neutral");break;case"escape":n.companyProfileOpen?N():n.detailModalOpen?R():n.modalOpen&&q(!1),n.sidebarOpen&&H(!1);break}});const E=o("#api-url");E&&E.addEventListener("click",()=>{const d=`${k}/news`;navigator.clipboard&&navigator.clipboard.writeText(d).then(()=>{E.textContent="Copied!",setTimeout(()=>{E.textContent=`${k}/news`},1500)})})}function O(e){n.filter.sentiment=e,M(".sentiment-filter-btn").forEach(t=>{t.classList.toggle("active",t.dataset.sentiment===e)}),w()}function H(e){const t=typeof e=="boolean"?e:!n.sidebarOpen;n.sidebarOpen=t;const s=o(".sidebar"),i=o("#sidebar-backdrop");s&&s.classList.toggle("open",t),i&&i.classList.toggle("open",t)}function q(e){n.modalOpen=e;const t=o("#modal-overlay");t&&t.classList.toggle("open",e),e&&M(".api-base-url").forEach(s=>{s.textContent=window.location.origin+window.location.pathname.replace(/\/[^/]*$/,"")})}function ze(e){n.detailItem=e,n.detailModalOpen=!0;const t=o("#detail-modal-overlay");if(!t)return;const s=n.userTier==="max";let i="";if(i+=`<div class="detail-article">
    <h3 class="detail-headline">${u(e.title||"Untitled")}</h3>
    <div class="detail-meta">
      <span class="source-tag">${u(e.source||"")}</span>
      <span class="detail-time">${V(e.published)} · ${ae(e.published)}</span>
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
    </div>`;else{const l=e.confidence!=null?Math.round(e.confidence*100):"—",r=(e.risk_level||"").toLowerCase(),c=r==="low"?"green":r==="high"?"red":"yellow",f=e.tradeable?"YES":"NO",p=e.tradeable?"yes":"no",h=(e.sentiment_label||"neutral").toLowerCase(),v=e.sentiment_score!=null?(e.sentiment_score>=0?"+":"")+Number(e.sentiment_score).toFixed(2):"—";i+=`<div class="detail-ticker-header">
      <div class="detail-ticker-symbol">${u(e.target_asset)}</div>
      <span class="detail-asset-type">${u(e.asset_type||"—")}</span>
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
        <div class="detail-metric-value detail-confidence">${l}%</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Risk Level</div>
        <div class="detail-metric-value">
          <span class="detail-risk ${c}">${u((e.risk_level||"—").toUpperCase())}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Tradeable</div>
        <div class="detail-metric-value">
          <span class="detail-tradeable ${p}">${f}</span>
        </div>
      </div>
    </div>
    <div class="detail-reasoning">
      <div class="detail-reasoning-label">Reasoning</div>
      <div class="detail-reasoning-text">${u(e.reasoning||"No reasoning provided.")}</div>
    </div>`}const a=t.querySelector(".detail-modal-body");a&&(a.innerHTML=i),t.classList.add("open")}function R(){n.detailModalOpen=!1,n.detailItem=null;const e=o("#detail-modal-overlay");e&&e.classList.remove("open")}async function ve(e){n.companyProfileOpen=!0,n.companyProfileSymbol=e,n.companyProfileData=null,n.companyProfileLoading=!0,n.companyProfileActiveTab="fundamentals",n.companyProfileFinancials=null,n.companyProfileCompetitors=null,document.querySelectorAll(".cp-tab").forEach(a=>{a.classList.toggle("active",a.dataset.tab==="fundamentals")});const t=o("#company-profile-overlay");if(!t)return;const s=o("#company-profile-title");s&&(s.textContent=`// ${e.toUpperCase()}`);const i=o("#company-profile-body");i&&(i.innerHTML=`<div class="cp-loading">
      <div class="cp-loading-row"><div class="skeleton" style="width:60%;height:24px"></div></div>
      <div class="cp-loading-row"><div class="skeleton" style="width:40%;height:16px"></div></div>
      <div class="cp-loading-row" style="margin-top:16px"><div class="skeleton" style="width:100%;height:80px"></div></div>
      <div class="cp-loading-grid">
        <div class="skeleton" style="width:100%;height:64px"></div>
        <div class="skeleton" style="width:100%;height:64px"></div>
      </div>
    </div>`),t.classList.add("open");try{const a=await b.fetch(`${k}/market/${encodeURIComponent(e)}/details`);if(!a.ok){const r=await a.json().catch(()=>({}));throw new Error(r.message||`HTTP ${a.status}`)}const l=await a.json();n.companyProfileData=l,n.companyProfileLoading=!1,he(l)}catch(a){n.companyProfileLoading=!1,logger.warn("Error fetching company details for",e,a),i&&(i.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load company details for <strong>${u(e)}</strong></p>
        <span>${u(a.message)}</span>
      </div>`)}}function he(e){const t=o("#company-profile-body");if(!t)return;const s=e.logo_url?`<img class="cp-logo" src="${u(e.logo_url)}" alt="${u(e.name)}" onerror="this.style.display='none'">`:"",i=e.homepage_url?`<a class="cp-homepage" href="${u(e.homepage_url)}" target="_blank" rel="noopener noreferrer">${u(e.homepage_url.replace(/^https?:\/\//,""))}</a>`:"";t.innerHTML=`
    <div class="cp-header">
      ${s}
      <div class="cp-header-info">
        <div class="cp-name">${u(e.name||"—")}</div>
        <div class="cp-symbol-row">
          <span class="cp-symbol">${u(e.symbol||"—")}</span>
          ${e.sector?`<span class="cp-sector">${u(e.sector)}</span>`:""}
        </div>
      </div>
    </div>
    <div class="cp-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Market Cap</div>
        <div class="detail-metric-value">${Ee(e.market_cap)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Sector</div>
        <div class="detail-metric-value" style="font-size:12px">${u(e.sector||"—")}</div>
      </div>
    </div>
    ${e.description?`<div class="cp-description">
      <div class="cp-desc-label">About</div>
      <p class="cp-desc-text">${u(e.description)}</p>
    </div>`:""}
    ${i?`<div class="cp-links">${i}</div>`:""}
  `}function N(){n.companyProfileOpen=!1,n.companyProfileSymbol=null,n.companyProfileData=null,n.companyProfileLoading=!1,n.companyProfileActiveTab="fundamentals",n.companyProfileFinancials=null,n.companyProfileCompetitors=null;const e=o("#company-profile-overlay");e&&e.classList.remove("open")}async function Xe(e){if(!e)return;const t=o("#company-profile-body");if(t){if(n.companyProfileFinancials){Z(n.companyProfileFinancials);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:60%;height:24px"></div></div>
    <div class="cp-loading-grid">
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
      <div class="skeleton" style="width:100%;height:64px"></div>
    </div>
    <div class="cp-loading-row" style="margin-top:16px"><div class="skeleton" style="width:100%;height:120px"></div></div>
  </div>`;try{const s=await b.fetch(`${k}/market/${encodeURIComponent(e)}/financials`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileFinancials=i,n.companyProfileActiveTab==="financials"&&Z(i)}catch(s){logger.warn("Error fetching financials for",e,s),n.companyProfileActiveTab==="financials"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load financial data for <strong>${u(e)}</strong></p>
        <span>${u(s.message)}</span>
      </div>`)}}}function U(e){if(e==null)return"—";const t=Math.abs(e),s=e<0?"-":"";return t>=1e12?s+"$"+(t/1e12).toFixed(2)+"T":t>=1e9?s+"$"+(t/1e9).toFixed(2)+"B":t>=1e6?s+"$"+(t/1e6).toFixed(2)+"M":t>=1e3?s+"$"+(t/1e3).toFixed(2)+"K":s+"$"+t.toFixed(2)}function Z(e){const t=o("#company-profile-body");if(!t)return;const s=e.financials,i=e.earnings||[],a=s&&(s.revenue!=null||s.net_income!=null||s.eps!=null),l=i.length>0&&i.some(p=>p.actual_eps!=null);if(!a&&!l){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No financial data available</p>
      <span>Financial data is not available for this ticker (e.g., ETFs, indices).</span>
    </div>`;return}const r=s&&s.fiscal_period&&s.fiscal_year?`${s.fiscal_period} ${s.fiscal_year}`:"",c=a?`
    ${r?`<div class="cp-fin-period">Latest Quarter: ${u(r)}</div>`:""}
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
    </div>`:"";let f="";if(l){const p=[...i].reverse(),h=Math.max(...p.map(m=>Math.abs(m.actual_eps||0)),.01);f=`
    <div class="cp-fin-chart-section">
      <div class="cp-desc-label">Earnings Per Share — Last 4 Quarters</div>
      <div class="cp-bar-chart">${p.map(m=>{const g=m.actual_eps;if(g==null)return"";const $=Math.min(Math.abs(g)/h*100,100),I=g>=0?"cp-bar-positive":"cp-bar-negative",x=`${m.fiscal_period} ${String(m.fiscal_year).slice(-2)}`,T=m.estimated_eps!=null,F=T&&g>=m.estimated_eps,E=T?F?"cp-bar-beat":"cp-bar-miss":I;return`<div class="cp-bar-col">
        <div class="cp-bar-value ${E}">$${g.toFixed(2)}</div>
        <div class="cp-bar-track">
          <div class="cp-bar-fill ${E}" style="height:${$}%"></div>
        </div>
        <div class="cp-bar-label">${u(x)}</div>
        ${T?`<div class="cp-bar-est">Est: $${m.estimated_eps.toFixed(2)}</div>`:""}
      </div>`}).join("")}</div>
      <div class="cp-bar-legend">
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-positive"></span>Positive</span>
        <span class="cp-legend-item"><span class="cp-legend-dot cp-bar-negative"></span>Negative</span>
      </div>
    </div>`}t.innerHTML=c+f}async function Ye(e){if(!e)return;const t=o("#company-profile-body");if(t){if(n.companyProfileCompetitors){ee(n.companyProfileCompetitors);return}t.innerHTML=`<div class="cp-loading">
    <div class="cp-loading-row"><div class="skeleton" style="width:50%;height:24px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
    <div class="cp-loading-row"><div class="skeleton" style="width:100%;height:40px"></div></div>
  </div>`;try{const s=await b.fetch(`${k}/market/${encodeURIComponent(e)}/competitors`);if(!s.ok){const a=await s.json().catch(()=>({}));throw new Error(a.message||`HTTP ${s.status}`)}const i=await s.json();n.companyProfileCompetitors=i,n.companyProfileActiveTab==="competitors"&&ee(i)}catch(s){logger.warn("Error fetching competitors for",e,s),n.companyProfileActiveTab==="competitors"&&t&&(t.innerHTML=`<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load competitor data for <strong>${u(e)}</strong></p>
        <span>${u(s.message)}</span>
      </div>`)}}}function ee(e){const t=o("#company-profile-body");if(!t)return;const s=e.competitors||[];if(s.length===0){t.innerHTML=`<div class="cp-no-data">
      <div class="cp-no-data-icon">—</div>
      <p>No competitor data available</p>
      <span>Competitor information is not available for this ticker.</span>
    </div>`;return}const i=s.map(a=>{const l=a.change_percent!=null?a.change_percent:null,r=l!=null?l>=0?"positive":"negative":"",c=l!=null?`${l>=0?"+":""}${l.toFixed(2)}%`:"—",f=a.price!=null?`$${a.price.toFixed(2)}`:"—",p=U(a.market_cap),h=a.sector||"—";return`<tr class="cp-comp-row">
      <td class="cp-comp-ticker"><span class="cp-comp-ticker-link" data-ticker="${u(a.symbol)}">${u(a.symbol)}</span></td>
      <td class="cp-comp-name">${u(a.name)}</td>
      <td class="cp-comp-mcap">${p}</td>
      <td class="cp-comp-price">${f}</td>
      <td class="cp-comp-change ${r}">${c}</td>
      <td class="cp-comp-sector">${u(h)}</td>
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
    </div>`,t.querySelectorAll(".cp-comp-ticker-link[data-ticker]").forEach(a=>{a.addEventListener("click",()=>{ve(a.dataset.ticker)})})}function Ge(){if(typeof b>"u")return;b.init();const e=o("#btn-signin");e&&e.addEventListener("click",()=>{b.showAuthModal("signin")});const t=o("#btn-signout");t&&t.addEventListener("click",()=>{b.signOut()});const s=o("#btn-user"),i=o("#user-dropdown");s&&i&&(s.addEventListener("click",a=>{a.stopPropagation(),i.classList.toggle("open")}),document.addEventListener("click",()=>{i.classList.remove("open")})),b.onAuthChange(a=>{Je(a)})}function Je(e){const t=o("#btn-signin"),s=o("#user-menu");if(e){t&&(t.style.display="none"),s&&(s.style.display="flex");const i=o("#user-avatar"),a=o("#user-name"),l=o("#dropdown-email");i&&e.photoURL&&(i.src=e.photoURL,i.alt=e.displayName||""),a&&(a.textContent=e.displayName||e.email||""),l&&(l.textContent=e.email||""),Ke()}else t&&(t.style.display="flex"),s&&(s.style.display="none"),ge()}async function Ke(){try{const e=await b.fetch(`${k}/auth/tier`);if(!e.ok)return;const t=await e.json(),s=t.tier||"free",i=s==="plus"?"pro":s,a=t.features||{};n.userTier=i,n.userFeatures=a,W(),S(),w(),j(),Ce();const l=o("#tier-badge"),r=o("#dropdown-tier");if(l&&(l.textContent=i.toUpperCase(),l.className="tier-badge"+(i!=="free"?" "+i:"")),r){const c={free:"Free Plan",pro:"Pro Plan",plus:"Pro Plan"};r.textContent=c[i]||"Free Plan"}a.terminal_access===!1||i==="free"?ge():Qe()}catch{}}function ge(){if(o("#upgrade-gate"))return;const e=document.createElement("div");e.id="upgrade-gate",e.style.cssText="position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(1,4,9,0.95);",e.innerHTML='<div style="text-align:center;max-width:420px;padding:40px;border:1px solid rgba(48,54,61,0.8);border-radius:12px;background:#0d1117;"><h2 style="color:#e6edf3;margin:0 0 12px;font-size:22px;">Upgrade to Pro</h2><p style="color:#8b949e;margin:0 0 24px;line-height:1.6;">The SIGNAL terminal requires a Pro subscription. Get full access to real-time news, sentiment analysis, and deduplication.</p><a href="/pricing" style="display:inline-block;padding:10px 28px;background:#238636;color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">View Plans</a><div style="margin-top:16px;"><a href="/" style="color:#8b949e;font-size:13px;text-decoration:underline;">Back to home</a></div></div>',document.body.appendChild(e),me(),re()}function Qe(){const e=o("#upgrade-gate");e&&e.remove()}function te(){_e(),Pe(),Ae(),S(),He(),fe(),We(),Q(),Ge(),setInterval(Q,1e3),_(),B(),Y(),pe(),setInterval(()=>{B(),Y()},3e4)}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",te):te();document.addEventListener("DOMContentLoaded",function(){var e=document.getElementById("auth-gate"),t=document.getElementById("auth-gate-signin");function s(){typeof SignalAuth<"u"&&SignalAuth.isSignedIn()?e.classList.add("hidden"):e.classList.remove("hidden")}t&&t.addEventListener("click",function(){typeof SignalAuth<"u"&&SignalAuth.showAuthModal("signin")}),typeof SignalAuth<"u"&&SignalAuth.onAuthChange(s),setTimeout(function(){typeof SignalAuth<"u"&&(SignalAuth.onAuthChange(s),s())},500)});

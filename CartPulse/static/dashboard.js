"use strict";
const el = id => document.getElementById(id);
const textNode = (tag, value, cls) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  node.textContent = value;
  return node;
};
const fmt = new Intl.NumberFormat("en-IN",{maximumFractionDigits:0});
const money = n => "₹"+fmt.format(n);
function shortMoney(n) {
  const abs=Math.abs(n);
  const unit=abs>=1e7?[1e7,"Cr"]:abs>=1e5?[1e5,"L"]:abs>=1e3?[1e3,"K"]:[1,""];
  return "₹"+new Intl.NumberFormat("en-IN",{maximumFractionDigits:unit[0]===1?0:2}).format(n/unit[0])+unit[1];
}
const pct = n => Number(n).toFixed(1)+"%";
const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const palette=["#285c44","#548664","#8bab79","#bbcf91","#dfa379","#879bab"];
const names={overview:["Overview","Warehouse overview","Track revenue, orders and customer loyalty across Pune’s six micro-markets."],
  retention:["Customer retention","Customer retention","Explore repeat purchasing from each customer’s first month onward."],
  zones:["Pune zones","Pune zone insights","Compare delivery demand, revenue share and buyer loyalty by Pune micro-market."],
  explorer:["SQL Explorer","Data Warehouse & SQL Explorer","Explore the star schema and query the live Pune commerce warehouse."]};
const queryNames={kpis:"Summary metrics",trend:"Revenue & order trend",categories:"Category performance",zones:"Pune zone performance",cohorts:"Customer retention cohorts",peaks:"Monthly revenue ranking"};
let data, controller, requestId=0, chartsReady=false;
const charts={};
function icon(id){return '<svg aria-hidden="true"><use href="#'+id+'"></use></svg>';}
function showPage(){
  const page=Object.hasOwn(names,location.hash.slice(1))?location.hash.slice(1):"overview";
  document.querySelectorAll(".page").forEach(section=>section.hidden=section.id!==page);
  document.querySelectorAll("nav a").forEach(link=>{
    link.classList.toggle("active",link.dataset.page===page);
    if(link.dataset.page===page)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current");
  });
  [el("crumb").textContent,el("title").textContent,el("intro").textContent]=names[page];
  document.body.classList.remove("menu-open");el("menu-toggle").setAttribute("aria-expanded","false");
  if(page==="overview"&&data&&chartsReady) drawCharts();
  window.scrollTo(0,0);
}
window.addEventListener("hashchange",showPage);
el("menu-toggle").onclick=()=>el("menu-toggle").setAttribute("aria-expanded",String(document.body.classList.toggle("menu-open")));
document.addEventListener("keydown",event=>{if(event.key==="Escape"){document.body.classList.remove("menu-open");el("menu-toggle").setAttribute("aria-expanded","false");}});
function connected(ok){
  el("dot").classList.toggle("on",ok);el("dbstate").textContent=ok?"Connected":"Disconnected";
  el("live").parentElement.classList.toggle("online",ok);el("live").textContent=ok?"Warehouse online":"Offline";
}
async function get(url,options={}){
  const res=await fetch(url,options);
  const body=await res.json();
  if(!res.ok)throw Error(typeof body.detail==="string"?body.detail:"The request could not be completed.");
  return body;
}
function addOption(id,value,label){el(id).add(new Option(label,value));}
async function init(){
  try{
    const filters=await get("/api/filters");
    el("engine-name").textContent=filters.engine==="SQLite"?"SQLite demo replica":"MySQL warehouse";
    el("engine-chip").textContent=filters.engine==="SQLite"?"SQLite":"InnoDB";
    filters.zones.forEach(z=>addOption("zone",z.region_key,z.zone_name));
    filters.categories.forEach(c=>addOption("category",c,c));
    filters.years.forEach(y=>{addOption("period",y,"Year "+y);for(let q=1;q<=4;q++)addOption("period",y+"-"+q,"Q"+q+" · "+y);});
    if(filters.years.length)el("period").value=String(filters.years[0]);
    await refresh();
  }catch(e){fail(e);}
}
function fail(e){connected(false);el("status").hidden=false;el("status").textContent=e.message+" ";const retry=textNode("button","Retry");retry.onclick=()=>location.reload();el("status").append(retry);}
async function refresh(){
  const rev=++requestId;
  if(controller)controller.abort();controller=new AbortController();
  const params=new URLSearchParams();
  ["zone","category"].forEach(id=>{if(el(id).value)params.set(id,el(id).value);});
  const [year,quarter]=el("period").value.split("-");
  if(year)params.set("year",year);if(quarter)params.set("quarter",quarter);
  el("reset").hidden=!(el("zone").value||el("category").value||el("period").value);
  el("live").textContent="Refreshing";el("main").setAttribute("aria-busy","true");
  try{
    const next=await get("/api/dashboard?"+params,{signal:controller.signal});
    if(rev!==requestId)return;
    data=next;connected(true);el("status").hidden=true;render();
  }catch(e){if(e.name!=="AbortError"&&rev===requestId)fail(e);}
  finally{if(rev===requestId)el("main").setAttribute("aria-busy","false");}
}
["zone","category","period"].forEach(id=>el(id).onchange=refresh);
el("reset").onclick=()=>{["zone","category","period"].forEach(id=>el(id).value="");refresh();};
function spark(values,color){
  const nums=values.map(Number),max=Math.max(...nums,0),min=Math.min(...nums,0),range=max-min||1;
  const path=nums.map((v,i)=>(i*74/Math.max(nums.length-1,1)).toFixed(1)+","+(25-(v-min)*22/range).toFixed(1)).join(" ");
  return '<svg class="spark" aria-hidden="true" viewBox="-1 0 77 28"><polygon points="0,27 '+path+' 74,27" fill="'+color+'" opacity=".12" stroke="none"/><polyline points="'+path+'" fill="none" stroke="'+color+'"/></svg>';
}
function metric(label,value,note,key,symbol,index){
  const div=document.createElement("article");div.className="metric"+(index===0?" primary":"");
  div.innerHTML='<div class="metric-top"><span class="metric-icon">'+icon(symbol)+'</span>'+label+'</div><div class="metric-value"></div><div class="metric-bottom"><span class="metric-note"></span>'+spark(data.trend.map(r=>r[key]),["#c7ef9c","#599b71","#c2925e","#9a81ac"][index])+'</div>';
  div.querySelector(".metric-value").textContent=value;
  div.querySelector(".metric-note").textContent=note;
  return div;
}
function table(container,headers,rows){
  const t=document.createElement("table"),head=t.createTHead().insertRow(),body=t.createTBody();
  headers.forEach(h=>{const th=textNode("th",h);th.scope="col";head.append(th);});
  rows.forEach(row=>{const tr=body.insertRow();row.forEach(value=>{const td=tr.insertCell();if(value instanceof Node)td.append(value);else td.textContent=value??"—";});});
  container.replaceChildren(t);
  if(!rows.length)container.append(textNode("p","No matching records.","note"));
  return t;
}
function cohort(){
  if(!data.trend.length||!data.cohorts.length){el("cohort-table").textContent="No cohorts in this selection.";return;}
  const idx=(year,month)=>year*12+Number(month)-1;
  const last=data.trend.at(-1),end=idx(last.year,last.month_number);
  const groups=new Map();
  data.cohorts.forEach(row=>{if(!groups.has(row.cohort))groups.set(row.cohort,{size:row.members,cells:{}});groups.get(row.cohort).cells[row.age]=Number(row.retention_pct);});
  const keys=[...groups.keys()], first=keys[0].split("-"), n=end-idx(Number(first[0]),first[1])+1;
  const rows=keys.map(key=>{
    const [year,month]=key.split("-").map(Number), group=groups.get(key);
    return [months[month-1]+" "+year,fmt.format(group.size),...Array.from({length:n},(_,i)=>i>end-idx(year,month)?"—":pct(group.cells[i]||0))];
  });
  const t=table(el("cohort-table"),["Cohort","Buyers",...Array.from({length:n},(_,i)=>"M"+i)],rows);
  [...t.tBodies[0].rows].forEach(row=>[...row.cells].slice(2).forEach(td=>{
    const val=parseFloat(td.textContent);td.className="heat";if(!Number.isNaN(val)){td.style.backgroundColor="hsl(145 28% "+(96-val*.67)+"%)";td.style.color=val>66?"#fff":"#244332";}
  }));
}
function render(){
  const k=data.kpis;
  el("metrics").replaceChildren(
    metric("Total revenue",shortMoney(k.revenue_inr),"Net of discounts","revenue_inr","rupee",0),
    metric("Total orders",fmt.format(k.orders),fmt.format(k.buyers)+" unique buyers","orders","bag",1),
    metric("Avg. order value",money(k.aov_inr),"Revenue per order","aov_inr","wallet",2),
    metric("Repeat buyer rate",pct(k.repeat_pct),fmt.format(k.repeat_buyers)+" repeat buyers","repeat_pct","users",3));
  el("metrics").firstChild.querySelector(".metric-value").title=money(k.revenue_inr);
  el("donut-total").textContent=shortMoney(k.revenue_inr);
  el("zone-legend").replaceChildren(...data.zones.map(z=>{
    const row=document.createElement("div"), swatch=textNode("i","","swatch");swatch.style.background=palette[z.region_key-1];
    row.append(swatch,textNode("span",z.zone_name),textNode("b",pct(z.share_pct)));return row;
  }));
  el("peak").replaceChildren();el("peak").innerHTML=icon("bars");
  const top=data.peaks[0];el("peak").append(document.createTextNode(Number(k.orders)&&top?
    months[top.month_number-1]+" "+top.year+" led the period with "+money(top.revenue_inr)+" in revenue.":"No orders match these filters."));
  table(el("zone-summary"),["Pune zone","Orders","Repeat rate"],data.zones.map(z=>[z.zone_name,fmt.format(z.orders),pct(z.repeat_pct)]));
  table(el("zone-details"),["Delivery zone","PIN code","Orders","Repeat rate","Revenue","Share"],data.zones.map(z=>[z.zone_name,z.pin_code,fmt.format(z.orders),pct(z.repeat_pct),money(z.revenue_inr),pct(z.share_pct)]));
  cohort();showQuery();
  el("updated").textContent="Updated "+new Intl.DateTimeFormat("en-IN",{timeZone:"Asia/Kolkata",hour:"2-digit",minute:"2-digit",day:"numeric",month:"short"}).format(new Date(data.as_of))+" IST";
  if(chartsReady&&!el("overview").hidden)drawCharts();
}
function makeChart(id,config){if(charts[id])charts[id].destroy();charts[id]=new Chart(el(id),config);}
function drawCharts(){
  Chart.defaults.font.family='"DM Sans","Segoe UI",sans-serif';Chart.defaults.color="#5f7166";Chart.defaults.font.size=12;
  const common={responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}}};
  const grid={color:"#e7ece5",drawTicks:false}, ticks={padding:7,maxTicksLimit:6};
  const series=data.trend, zones=data.zones, cats=data.categories;
  makeChart("trend-chart",{type:"bar",data:{labels:series.map(r=>months[r.month_number-1]+(series.length>12?" "+r.year:"")),datasets:[
    {type:"line",label:"Orders",data:series.map(r=>Number(r.orders)),yAxisID:"orders",borderColor:"#d99255",backgroundColor:"#d99255",pointRadius:3,pointHoverRadius:5,pointBorderWidth:1.3,pointBorderColor:"#fff",borderWidth:2.5,tension:.3,order:0},
    {label:"Revenue",data:series.map(r=>Number(r.revenue_inr)),backgroundColor:series.map(r=>[8,9,10,11].includes(r.month_number)?"#31674e":"#73977c"),borderRadius:4,maxBarThickness:35,barPercentage:.83,yAxisID:"revenue",order:1}]},
    options:{...common,interaction:{mode:"index",intersect:false},plugins:{...common.plugins,tooltip:{callbacks:{label:item=>item.dataset.label+" · "+(item.datasetIndex===1?money(item.parsed.y):fmt.format(item.parsed.y)),afterBody:items=>{const m=series[items[0].dataIndex].month_number;return [8,9].includes(m)?"Ganesh festival season":[10,11].includes(m)?"Diwali shopping season":"";}}}},scales:{
      x:{grid:{display:false},border:{display:false},ticks:{maxRotation:0,autoSkip:true}},
      revenue:{position:"left",beginAtZero:true,grid,border:{display:false},ticks:{...ticks,callback:shortMoney}},
      orders:{position:"right",beginAtZero:true,grid:{display:false},border:{display:false},ticks:{...ticks,precision:0,callback:v=>fmt.format(v)}}}}});
  makeChart("zone-chart",{type:"doughnut",data:{labels:zones.map(z=>z.zone_name),datasets:[{data:zones.map(z=>Number(z.revenue_inr)),backgroundColor:zones.map(z=>palette[z.region_key-1]),borderColor:"#fff",borderWidth:3,hoverOffset:3}]},options:{...common,cutout:"76%",plugins:{...common.plugins,tooltip:{callbacks:{label:i=>money(i.raw)+" · "+pct(zones[i.dataIndex].share_pct)}}}}});
  makeChart("category-chart",{type:"bar",data:{labels:cats.map(c=>c.category.split(" & ")),datasets:[
    {label:"Revenue",xAxisID:"sales",data:cats.map(c=>Number(c.revenue_inr)),backgroundColor:"#4d8161",borderRadius:3,maxBarThickness:12},
    {label:"Margin",xAxisID:"margin",data:cats.map(c=>Number(c.margin_pct)),backgroundColor:"#d6a075",borderRadius:3,maxBarThickness:8}]},
    options:{...common,indexAxis:"y",plugins:{...common.plugins,tooltip:{callbacks:{label:i=>i.dataset.label+" · "+(i.datasetIndex?pct(i.raw):money(i.raw))}}},scales:{
      y:{grid:{display:false},border:{display:false},ticks:{autoSkip:false,font:{size:11}}},
      sales:{position:"bottom",beginAtZero:true,grid,border:{display:false},ticks:{maxTicksLimit:5,callback:shortMoney}},
      margin:{position:"top",min:0,max:100,grid:{display:false},border:{display:false},ticks:{maxTicksLimit:5,callback:v=>v+"%"}}}}});
}
function showQuery(){
  const q=data?.queries[el("query-type").value];if(!q)return;
  const pre=el("query-source");pre.replaceChildren();
  q.sql.split(/\b(SELECT|WITH|FROM|JOIN|LEFT|ON|WHERE|GROUP BY|COUNT|SUM|AVG|OVER|ORDER BY|AS|PARTITION BY|RANK|LAG|FIRST_VALUE|LIMIT|DISTINCT|USING)\b/gi).forEach((part,i)=>pre.append(i%2?textNode("span",part,"keyword"):document.createTextNode(part)));
  el("query-args").textContent="Bound parameters · "+JSON.stringify(q.parameters);
}
Object.entries(queryNames).forEach(([key,label])=>addOption("query-type",key,label));el("query-type").onchange=showQuery;
const schema=el("schema");
function schemaBox(name,info,cls){const box=textNode("div","",cls);box.append(textNode("strong",name),textNode("small",info));return box;}
schema.append(schemaBox("fact_orders","PK order_id · 4 foreign keys","schema-fact"));
[["dim_customers","customer_key"],["dim_products","product_key"],["dim_regions","region_key"],["dim_date","date_key"]].forEach(([name,key],i)=>{const conn=textNode("div","","connector");conn.style.gridRow=i+1;conn.title="Many orders to one dimension row";schema.append(conn);const box=schemaBox(name,"PK "+key,"schema-dim");box.style.gridRow=i+1;schema.append(box);});
el("run").onclick=async()=>{
  const button=el("run");button.disabled=true;el("sql-status").textContent="Running query…";el("results").replaceChildren();
  try{const result=await get("/api/sandbox",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sql:el("sql").value})});
    table(el("results"),result.columns,result.rows.map(r=>result.columns.map(c=>{
      const v=r[c];if(v===null)return "NULL";
      if(/inr|revenue|unit_price|unit_cost/i.test(c)&&Number.isFinite(Number(v)))return money(v);
      if(/pct/i.test(c)&&Number.isFinite(Number(v)))return pct(v);return v;
    })));el("sql-status").textContent=result.truncated?"Showing the first 200 rows.":result.rows.length+" rows returned.";
  }catch(e){el("sql-status").textContent=e.message;}finally{button.disabled=false;}
};
showPage();init();
function loadCharts(){
  let fallback=false,done=false;
  function ready(){if(!window.Chart||done)return;done=true;chartsReady=true;if(data&&!el("overview").hidden)drawCharts();}
  function script(src,onerror){const s=document.createElement("script");s.src=src;s.onload=ready;s.onerror=onerror;document.head.append(s);}
  function local(){if(done||fallback)return;fallback=true;script("/static/vendor/chart.umd.min.js",()=>{el("status").hidden=false;el("status").textContent="Charts could not load. Reload the dashboard to retry.";});}
  script("https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js",local);setTimeout(local,700);
}
loadCharts();

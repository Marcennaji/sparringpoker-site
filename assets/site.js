
(function(){
  var base=(document.body && document.body.getAttribute('data-base'))||'';
  var versionData=null;
  function renderVersionBadge(lang){
    document.querySelectorAll('.version-badge').forEach(function(badge){
      if(!versionData||!versionData.latest_version)return;
      var dateStr='';
      if(versionData.release_date){var d=new Date(versionData.release_date+'T12:00:00');dateStr=d.toLocaleDateString(lang==='fr'?'fr-FR':'en-US',{month:'short',day:'numeric',year:'numeric'});}
      var whatsNew=lang==='fr'?'Nouveautés →':'What’s new? →';
      badge.innerHTML='<strong>v'+versionData.latest_version+'</strong>'+(dateStr?'<br>'+dateStr:'')+'<br>'+whatsNew;
      badge.style.display='inline-block';
    });
  }
  window.setLang=function(lang,button){
    localStorage.setItem('lang',lang);document.documentElement.lang=lang;
    document.querySelectorAll('.lang-btn').forEach(function(btn){var active=btn.getAttribute('data-lang-flag')===lang;btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',active?'true':'false');});
    document.querySelectorAll('[data-lang]').forEach(function(el){el.classList.toggle('active',el.getAttribute('data-lang')===lang);});
    var skip=document.querySelector('.skip-link');if(skip)skip.textContent=lang==='fr'?'Aller au contenu':'Skip to content';
    renderVersionBadge(lang);
  };
  function init(){
    var saved=localStorage.getItem('lang')||'en';
    window.setLang(saved);
    document.querySelectorAll('.lang-btn').forEach(function(btn){btn.addEventListener('click',function(){window.setLang(btn.getAttribute('data-lang-flag'),btn);});});
    document.querySelectorAll('[data-user][data-domain]').forEach(function(link){var email=link.getAttribute('data-user')+'@'+link.getAttribute('data-domain');link.href='mailto:'+email;link.textContent=email;});
    document.querySelectorAll('[data-current-year]').forEach(function(el){el.textContent=new Date().getFullYear();});
    fetch(base+'assets/version.json').then(function(r){return r.json();}).then(function(data){versionData=data;renderVersionBadge(saved);}).catch(function(){});
    var isMobile=/android|iphone|ipad|ipod|mobile/i.test(navigator.userAgent);
    if(isMobile){document.body.classList.add('is-mobile');}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

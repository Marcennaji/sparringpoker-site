
(function(){
  var versionData=null;
  function savedLanguage(){
    try{
      if(window.localStorage.getItem('lang')==='fr')return 'fr';
    }catch(error){
      // Storage can be unavailable even when scripts are enabled.
    }
    return 'en';
  }
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
  function setLang(lang){
    document.documentElement.lang=lang;
    document.querySelectorAll('.lang-btn').forEach(function(btn){var active=btn.getAttribute('data-lang-flag')===lang;btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',active?'true':'false');});
    document.querySelectorAll('[data-src-en][data-src-fr]').forEach(function(el){el.src=el.getAttribute('data-src-'+lang);});
    document.querySelectorAll('[data-href-en][data-href-fr]').forEach(function(el){el.href=el.getAttribute('data-href-'+lang);});
    var skip=document.querySelector('.skip-link');if(skip)skip.textContent=lang==='fr'?'Aller au contenu':'Skip to content';
    renderVersionBadge(lang);
  }
  function init(){
    setLang(savedLanguage());
    document.querySelectorAll('.lang-btn').forEach(function(btn){
      btn.addEventListener('click',function(){
        var lang=btn.getAttribute('data-lang-flag');
        setLang(lang);
        try{
          window.localStorage.setItem('lang',lang);
        }catch(error){
          // The selection still works for this page without storage.
        }
      });
    });
    document.querySelectorAll('[data-current-year]').forEach(function(el){el.textContent=new Date().getFullYear();});
    var base=document.body.getAttribute('data-base')||'';
    fetch(base+'assets/version.json').then(function(r){return r.json();}).then(function(data){versionData=data;renderVersionBadge(document.documentElement.lang);}).catch(function(){});
    var userAgentPlatform=navigator.userAgentData&&navigator.userAgentData.platform;
    var isAndroidPhone=/android/i.test(userAgentPlatform||'')||/android/i.test(navigator.userAgent);
    if(isAndroidPhone){document.body.classList.add('is-android-phone');}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

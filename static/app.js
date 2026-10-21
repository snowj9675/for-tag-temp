// Preview only on deliberate hover; never preload hundreds of videos.
document.querySelectorAll('.thumb[data-preview], .thumb').forEach(card=>{
  const img=card.querySelector('img[data-preview]');
  if(!img)return;
  const url=img.dataset.preview;
  if(!url)return;
  let timer=null,video=null;
  function clear(){
    clearTimeout(timer);timer=null;
    if(video){video.pause();video.removeAttribute('src');video.load();video.remove();video=null;}
  }
  card.addEventListener('pointerenter',e=>{
    if(e.pointerType==='touch')return;
    timer=setTimeout(()=>{
      video=document.createElement('video');
      video.muted=true;video.loop=true;video.playsInline=true;
      video.preload='none';video.src=url;
      video.setAttribute('aria-hidden','true');
      card.appendChild(video);
      video.play().catch(()=>clear());
    },600);
  });
  card.addEventListener('pointerleave',clear);
  card.addEventListener('focusout',clear);
});
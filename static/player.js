(() => {
  const video = document.querySelector('#main-video');
  const button = document.querySelector('#load-video');
  const status = document.querySelector('#player-status');
  if (!video || !button || !status) return;
  let hls = null;
  const show = message => { status.textContent = message; };

  button.addEventListener('click', async () => {
    button.disabled = true;
    show('Loading video source…');
    try {
      const resp = await fetch(video.dataset.resolve, {cache: 'no-store'});
      const data = await resp.json();
      if (!resp.ok || !data.url) throw new Error(data.error || 'Source unavailable');
      video.hidden = false;
      if (data.type === 'hls') {
        if (video.canPlayType('application/vnd.apple.mpegurl')) {
          video.src = data.url;
        } else if (window.Hls && window.Hls.isSupported()) {
          hls = new window.Hls({enableWorker: true});
          hls.loadSource(data.url);
          hls.attachMedia(video);
          hls.on(window.Hls.Events.ERROR, (_, info) => {
            if (info.fatal) show('Streaming error. The host may block cross-origin playback.');
          });
        } else {
          throw new Error('HLS playback is not supported by this browser');
        }
      } else {
        video.src = data.url;
      }
      button.hidden = true;
      show('');
      await video.play().catch(() => { show('Press play to start the video.'); });
    } catch (err) {
      show(err.message || 'Unable to load video');
      button.disabled = false;
    }
  });
  window.addEventListener('pagehide', () => { if (hls) hls.destroy(); });
})();

/* ============================================================
   IlmNote — Modern UI Interactions
   ============================================================ */

/* ---------- Sidebar ---------- */
const menuBtn = document.getElementById('menuToggle');
const sidebar = document.getElementById('sidebar');
if (menuBtn && sidebar) {
  menuBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 900 && sidebar.classList.contains('open')
        && !sidebar.contains(e.target) && !menuBtn.contains(e.target)) {
      sidebar.classList.remove('open');
    }
  });
}

/* ---------- Theme toggle ---------- */
const themeBtn = document.getElementById('themeToggle');
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  // Update icon
  const icon = themeBtn?.querySelector('use');
  if (icon) icon.setAttribute('href', theme === 'dark' ? '#i-sun' : '#i-moon');
}
themeBtn?.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  fetch('/settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'theme=' + next
  });
});
// Init icon based on current theme
applyTheme(document.documentElement.getAttribute('data-theme'));

/* ---------- Bookmark / Favorite ---------- */
document.querySelectorAll('.toggle-bm').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    btn.disabled = true;
    const id = btn.dataset.id;
    const res = await fetch(`/toggle/bookmark/${id}`, {method:'POST'});
    const j = await res.json();
    btn.classList.toggle('active', j.state);
    btn.disabled = false;
  });
});
document.querySelectorAll('.toggle-fav').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    btn.disabled = true;
    const id = btn.dataset.id;
    const res = await fetch(`/toggle/favorite/${id}`, {method:'POST'});
    const j = await res.json();
    btn.classList.toggle('active', j.state);
    btn.disabled = false;
  });
});

/* ---------- Reader buttons ---------- */
const bmBtn = document.getElementById('bmBtn');
bmBtn?.addEventListener('click', async () => {
  const id = bmBtn.dataset.id;
  const res = await fetch(`/toggle/bookmark/${id}`, {method:'POST'});
  const j = await res.json();
  bmBtn.classList.toggle('active', j.state);
});
const favBtn = document.getElementById('favBtn');
favBtn?.addEventListener('click', async () => {
  const id = favBtn.dataset.id;
  const res = await fetch(`/toggle/favorite/${id}`, {method:'POST'});
  const j = await res.json();
  favBtn.classList.toggle('active', j.state);
});

/* ---------- Font size controls ---------- */
let fontSize = parseFloat(getComputedStyle(document.documentElement)
  .getPropertyValue('--font-size')) || 18;

document.getElementById('fontInc')?.addEventListener('click', () => {
  fontSize = Math.min(32, fontSize + 1);
  document.documentElement.style.setProperty('--font-size', fontSize + 'px');
  localStorage.setItem('reader_font', fontSize);
});
document.getElementById('fontDec')?.addEventListener('click', () => {
  fontSize = Math.max(12, fontSize - 1);
  document.documentElement.style.setProperty('--font-size', fontSize + 'px');
  localStorage.setItem('reader_font', fontSize);
});

/* ---------- Fullscreen ---------- */
document.getElementById('fullscreenBtn')?.addEventListener('click', () => {
  const el = document.getElementById('reader');
  if (!document.fullscreenElement) {
    el?.requestFullscreen?.().catch(() => el?.classList.toggle('fullscreen-fallback'));
  } else {
    document.exitFullscreen?.();
  }
});

/* ---------- View mode switch ---------- */
document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const grid = document.getElementById('articlesGrid');
    if (!grid) return;
    grid.dataset.view = btn.dataset.view;
    document.querySelectorAll('.view-btn').forEach(b => b.classList.toggle('active', b === btn));
    localStorage.setItem('view_mode', btn.dataset.view);
  });
});
// Restore view mode
const grid = document.getElementById('articlesGrid');
if (grid) {
  const savedView = localStorage.getItem('view_mode') || grid.dataset.view || 'grid';
  grid.dataset.view = savedView;
  document.querySelectorAll('.view-btn').forEach(b => b.classList.toggle('active', b.dataset.view === savedView));
}

/* ---------- Restore font size ---------- */
const savedFont = localStorage.getItem('reader_font');
if (savedFont) {
  document.documentElement.style.setProperty('--font-size', savedFont + 'px');
}

/* ---------- Card click animation feedback ---------- */
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('mousedown', () => card.style.transform = 'translateY(-2px) scale(0.995)');
  card.addEventListener('mouseup', () => card.style.transform = '');
  card.addEventListener('mouseleave', () => card.style.transform = '');
});

/* ============================================================
   Reader — Tools, Reading Time, Font Scale, Fullscreen, FAB
   ============================================================ */
/* ---------- Tools dropdown (sticky) ---------- */
const toolsToggle = document.getElementById('toolsToggle');
const toolsPanel = document.getElementById('toolsPanel');
const toolsRail = document.getElementById('toolsRail');

if (toolsToggle && toolsPanel && toolsRail) {
  function openTools() {
    toolsToggle.setAttribute('aria-expanded', 'true');
    toolsPanel.hidden = false;
  }
  function closeTools() {
    toolsToggle.setAttribute('aria-expanded', 'false');
    toolsPanel.hidden = true;
  }

  toolsToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = toolsToggle.getAttribute('aria-expanded') === 'true';
    if (open) closeTools(); else openTools();
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!toolsRail.contains(e.target)) closeTools();
  });

  // Close on ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTools();
  });

  // Close panel when user starts scrolling far (optional, feels clean)
  let scrollTimer = null;
  window.addEventListener('scroll', () => {
    if (toolsPanel.hidden) return;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      // keep open during tiny scrolls; close after big movement
    }, 150);
  }, { passive: true });
}

/* ---------- Font size controls: only scale the article body ---------- */
let readerScale = parseFloat(localStorage.getItem('reader_scale')) || 1;
function applyReaderScale() {
  document.documentElement.style.setProperty('--reader-scale', readerScale);
  localStorage.setItem('reader_scale', readerScale);
}
applyReaderScale();

document.getElementById('fontInc')?.addEventListener('click', () => {
  readerScale = Math.min(1.6, readerScale + 0.08);
  applyReaderScale();
});
document.getElementById('fontDec')?.addEventListener('click', () => {
  readerScale = Math.max(0.75, readerScale - 0.08);
  applyReaderScale();
});

/* ---------- Fullscreen ---------- */
const fsBtn = document.getElementById('fullscreenBtn');
const readerEl = document.getElementById('reader');
if (fsBtn && readerEl) {
  fsBtn.addEventListener('click', async () => {
    try {
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        // Try native fullscreen first
        if (readerEl.requestFullscreen) {
          await readerEl.requestFullscreen();
        } else if (readerEl.webkitRequestFullscreen) {
          readerEl.webkitRequestFullscreen();
        } else {
          readerEl.classList.add('fullscreen-fallback');
        }
      } else {
        if (document.exitFullscreen) await document.exitFullscreen();
        else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
        readerEl.classList.remove('fullscreen-fallback');
      }
    } catch (err) {
      // Fallback if API fails (e.g. permissions, iframe)
      readerEl.classList.toggle('fullscreen-fallback');
    }
  });

  // Sync state when user presses ESC
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) {
      readerEl.classList.remove('fullscreen-fallback');
    }
  });
}

/* ---------- Reading Time (live counter) ---------- */
const rtBadge = document.getElementById('readingTimeBadge');
if (rtBadge) {
  const baseMinutes = parseInt(rtBadge.dataset.minutes) || 1;
  const startTime = Date.now();
  const textNode = rtBadge.querySelector('.rt-text');

  // Add pulsing dot when reading begins
  const dot = document.createElement('span');
  dot.className = 'dot';
  rtBadge.insertBefore(dot, textNode);

  function updateReadingTime() {
    const elapsed = Math.floor((Date.now() - startTime) / 1000); // seconds
    if (elapsed < 10) return;

    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;

    if (mins < 1) {
      textNode.textContent = `${secs} সেকেন্ড পড়া হচ্ছে`;
    } else {
      textNode.textContent = `${mins} মিনিট ${secs} সেকেন্ড পড়া হয়েছে`;
    }
    rtBadge.classList.add('live');
  }

  setInterval(updateReadingTime, 1000);
  updateReadingTime();
}

/* ---------- Floating Scroll FAB ---------- */
const fab = document.getElementById('scrollToggle');
if (fab) {
  const threshold = 400;

  function updateFab() {
    const scrollY = window.scrollY || window.pageYOffset;
    const docH = document.documentElement.scrollHeight;
    const winH = window.innerHeight;
    const atBottom = scrollY + winH >= docH - 80;

    if (scrollY > threshold) fab.classList.add('visible');
    else fab.classList.remove('visible');

    fab.classList.toggle('at-bottom', atBottom);
    fab.setAttribute('aria-label', atBottom ? 'উপরে যান' : 'নিচে যান');
  }

  fab.addEventListener('click', () => {
    const atBottom = fab.classList.contains('at-bottom');
    if (atBottom) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
    }
  });

  window.addEventListener('scroll', updateFab, { passive: true });
  window.addEventListener('resize', updateFab);
  updateFab();
}
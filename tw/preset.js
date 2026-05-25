/* Glass-flavored class presets used throughout the prototype.
   Exposed on window so any JSX file can compose them. */
window.G = {
  /* surfaces */
  card:       'bg-white/55 dark:bg-glass-dark-base backdrop-blur-3xl backdrop-saturate-150 border border-white/60 dark:border-white/10 shadow-glass shadow-glass-inner rounded-3xl',
  cardFlat:   'bg-white/55 dark:bg-glass-dark-base backdrop-blur-2xl backdrop-saturate-150 border border-white/60 dark:border-white/10 rounded-2xl',
  cardLg:     'bg-white/55 dark:bg-glass-dark-base backdrop-blur-3xl backdrop-saturate-150 border border-white/60 dark:border-white/10 shadow-glass-lg shadow-glass-inner rounded-[28px]',
  cardSoft:   'bg-white/35 dark:bg-white/5 backdrop-blur-2xl border border-white/50 dark:border-white/8 rounded-2xl',
  glassBar:   'bg-white/55 dark:bg-glass-dark-base backdrop-blur-3xl backdrop-saturate-150',

  /* tabs container */
  tabs:       'inline-flex gap-1 p-1.5 bg-white/40 dark:bg-white/5 backdrop-blur-2xl border border-white/60 dark:border-white/10 rounded-full shadow-glass-inner',
  tab:        'px-4 py-2 rounded-full text-[13px] font-semibold text-muted hover:text-ink dark:hover:text-white/90 transition-colors whitespace-nowrap inline-flex items-center gap-1.5',
  tabActive:  'bg-glass-grad dark:bg-glass-grad-dark text-ink dark:text-white shadow-glass-pill',

  /* buttons */
  btn:         'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-full text-[13px] font-semibold tracking-tight transition-all duration-200 active:scale-[0.98] hover:-translate-y-px',
  btnEmerald:  'bg-gradient-to-br from-[#00C480] to-[#008A57] text-white shadow-glow-emerald hover:shadow-[0_12px_28px_-6px_rgba(0,170,100,0.6),inset_0_1px_0_rgba(255,255,255,0.5)]',
  btnInk:      'bg-ink-grad text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.16),0_8px_24px_-8px_rgba(0,0,0,0.4)]',
  btnGhost:    'bg-white/40 dark:bg-white/5 backdrop-blur-xl border border-white/60 dark:border-white/10 text-ink dark:text-white/90 hover:bg-white/60 dark:hover:bg-white/10',
  btnSoft:     'bg-white/55 dark:bg-white/8 backdrop-blur-xl border border-white/60 dark:border-white/10 text-ink dark:text-white/90 hover:bg-white/75',
  btnSm:       'px-3 py-1.5 text-[12px]',
  btnLg:       'px-5 py-3 text-[14px]',

  /* icon button */
  iconBtn:     'inline-grid place-items-center w-9 h-9 rounded-xl text-ink-2 dark:text-white/70 hover:bg-white/60 dark:hover:bg-white/10 transition-colors',

  /* chips */
  chip:        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-medium bg-white/55 dark:bg-white/6 backdrop-blur-md border border-white/60 dark:border-white/10 text-ink-2 dark:text-white/80 cursor-pointer transition-colors hover:bg-white/80',
  chipActive:  'bg-gradient-to-br from-emerald-500/25 to-emerald-600/15 border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
  chipOutline: 'bg-transparent dark:bg-transparent border-ink/15 dark:border-white/15',

  /* badges (verification / moderation) */
  badgeBase:   'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]',
  badgeVerified: 'bg-emerald-500/18 text-emerald-700 dark:text-emerald-300',
  badgeModerated:'bg-blue-500/18 text-blue-700 dark:text-blue-300',
  badgePending: 'bg-amber-500/22 text-amber-700 dark:text-amber-300',
  badgeFlagged: 'bg-rose-500/18 text-rose-700 dark:text-rose-300',
  badgeAi:      'bg-violet-500/18 text-violet-700 dark:text-violet-300',

  /* input */
  input: 'w-full px-3.5 py-3 bg-white/55 dark:bg-white/6 border border-white/60 dark:border-white/10 backdrop-blur-md rounded-2xl text-[14px] text-ink dark:text-white placeholder:text-muted-2 dark:placeholder:text-white/40 outline-none focus:border-emerald-500/60 focus:ring-4 focus:ring-emerald-500/15 transition',

  /* text */
  eyebrow: 'text-[11px] font-semibold uppercase tracking-[0.08em] text-muted dark:text-white/60',
  meta:    'text-[12px] text-muted dark:text-white/60',
};

/* Feed + Reader — Tailwind */
const GF = window.G;
const IF = window.I;
const DF = window.DATA;

function Feed({ onOpenPost, toast }) {
  const [tab, setTab] = React.useState('for-you');
  const [composer, setComposer] = React.useState('');
  const [composerOpen, setComposerOpen] = React.useState(false);
  const [liked, setLiked] = React.useState(new Set(['p3']));
  const [saved, setSaved] = React.useState(new Set(['p4']));

  const tabs = [
    { id: 'for-you', name: 'Dành cho bạn', icon: 'Sparkle' },
    { id: 'follow',  name: 'Đang theo dõi', icon: 'Users' },
    { id: 'new',     name: 'Tin mới',     icon: 'Clock' },
    { id: 'trend',   name: 'Xu hướng',    icon: 'Flame' },
    { id: 'saved',   name: 'Đã lưu',      icon: 'Bookmark', count: saved.size },
  ];
  const sensitive = /chính trị|tin giả|fake/i.test(composer);

  const toggleLike = (id) => {
    const next = new Set(liked);
    if (next.has(id)) next.delete(id); else { next.add(id); toast('Đã thêm vào bài bạn thích.'); }
    setLiked(next);
  };
  const toggleSave = (id) => {
    const next = new Set(saved);
    if (next.has(id)) { next.delete(id); toast('Đã bỏ lưu.'); }
    else { next.add(id); toast('Đã lưu vào bộ sưu tập của bạn.'); }
    setSaved(next);
  };

  let posts = DF.POSTS;
  if (tab === 'saved') posts = posts.filter(p => saved.has(p.id));
  if (tab === 'new')   posts = [...posts].reverse();
  if (tab === 'trend') posts = [...posts].sort((a,b) => parseInt(b.stats.shares) - parseInt(a.stats.shares));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-8 max-w-[1180px] mx-auto px-8 py-6 pb-20" data-screen-label="04 Home Feed">
      <main className="min-w-0">
        {/* Composer */}
        <div className={`${GF.card} p-4 px-5 flex gap-3 mb-5`}>
          <Avatar author={DF.AUTHORS[0]} size="s40" />
          <div className="flex-1">
            <textarea
              placeholder="Bạn muốn chia sẻ tin tức hoặc góc nhìn gì hôm nay?"
              rows={composerOpen || composer ? 3 : 1}
              value={composer}
              onChange={e => setComposer(e.target.value)}
              onFocus={() => setComposerOpen(true)}
              className="w-full bg-transparent resize-none text-[15px] leading-snug outline-none placeholder:text-muted dark:placeholder:text-white/40"
            />
            {(composerOpen || composer) && composer.length > 12 && (
              <div className="flex flex-wrap gap-1.5 mt-2.5">
                <span className="text-[12px] text-muted dark:text-white/55 self-center mr-1">Gợi ý chủ đề:</span>
                <span className={`${GF.chip} ${GF.chipOutline}`}>#Công nghệ</span>
                <span className={`${GF.chip} ${GF.chipOutline}`}>#AI</span>
                <span className={`${GF.chip} ${GF.chipOutline}`}>#Báo chí số</span>
                <span className={GF.chip}><IF.Plus size={11}/> Thêm</span>
              </div>
            )}
            {sensitive && (
              <div className="mt-2.5 flex items-start gap-2.5 px-3.5 py-2.5 rounded-xl text-[12px] bg-gradient-to-br from-amber-500/22 to-amber-300/10 border border-amber-500/35 backdrop-blur-md text-amber-700 dark:text-amber-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]">
                <IF.AlertTriangle size={14} className="mt-0.5"/>
                <div>
                  <b className="block mb-0.5">Nội dung này có thể cần kiểm duyệt trước khi hiển thị công khai.</b>
                  Hãy đảm bảo bạn dẫn nguồn rõ ràng và tránh ngôn từ kích động. Đây chỉ là gợi ý, bài viết vẫn được lưu.
                </div>
              </div>
            )}
            <div className="flex items-center gap-2 pt-3 mt-3 border-t border-ink/8 dark:border-white/10 flex-wrap">
              <div className="flex gap-0.5">
                {['Image', 'Link', 'Tag', 'Group'].map(t => {
                  const Ic = IF[t];
                  return <button key={t} className="w-8 h-8 grid place-items-center rounded-lg text-muted hover:text-emerald-600 hover:bg-emerald-500/12 transition-colors"><Ic size={16}/></button>;
                })}
              </div>
              <span className="ml-auto text-[11.5px] text-muted dark:text-white/55">
                {composer.length > 0 ? `${composer.length} ký tự` : 'Hiển thị công khai · có kiểm duyệt'}
              </span>
              <button disabled={!composer.trim()} className={`${GF.btn} ${GF.btnEmerald} ${GF.btnSm} disabled:opacity-50`}>
                Đăng <IF.Send size={12}/>
              </button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-3 mb-5 flex-wrap">
          <div className={GF.tabs}>
            {tabs.map(t => {
              const Ic = IF[t.icon];
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`${GF.tab} ${tab === t.id ? GF.tabActive : ''}`}>
                  <Ic size={14}/> {t.name}
                  {t.count != null && <span className={`text-[10.5px] px-1.5 py-0.5 rounded-full ${tab === t.id ? 'bg-emerald-500/15 text-emerald-700' : 'bg-ink/8 dark:bg-white/10 text-muted'}`}>{t.count}</span>}
                </button>
              );
            })}
          </div>
          <span className="ml-auto inline-flex items-center gap-1 text-[12px] text-muted dark:text-white/55">
            <IF.Refresh size={13}/> Cập nhật 12 giây trước
          </span>
        </div>

        {tab === 'saved' && posts.length === 0 && (
          <div className={`${GF.card} text-center p-12`}>
            <IF.Bookmark size={28} className="mx-auto text-muted"/>
            <h4 className="font-serif text-[18px] font-medium mt-3 mb-1">Chưa có bài viết nào được lưu</h4>
            <p className="text-muted dark:text-white/55 text-[14px]">Lưu bài để đọc lại sau, dù khi không có mạng.</p>
          </div>
        )}

        {posts.map(p => (
          <PostCard key={p.id} post={p}
            liked={liked.has(p.id)} saved={saved.has(p.id)}
            onLike={() => toggleLike(p.id)}
            onSave={() => toggleSave(p.id)}
            onOpen={() => onOpenPost(p)}/>
        ))}

        {tab !== 'saved' && posts.length > 0 && (
          <button className={`${GF.btn} ${GF.btnGhost} w-full mt-2`}>
            <IF.Plus size={14}/> Xem thêm bài
          </button>
        )}
      </main>

      {/* Right rail */}
      <aside className="hidden lg:flex sticky top-[72px] flex-col gap-4 self-start">
        <div className={`${GF.card} p-5`}>
          <h4 className="font-serif text-[16px] font-medium mb-3.5 flex items-center gap-2"><IF.Flame size={16} className="text-emerald-500"/> Đang thịnh hành</h4>
          {DF.TRENDING.map((t, i) => (
            <div key={i} className={`flex items-start gap-3 py-2 cursor-pointer rounded-lg ${i ? 'border-t border-ink/8 dark:border-white/10' : ''}`}>
              <span className="font-serif italic text-[22px] text-muted-2 leading-none min-w-[22px]">{i + 1}</span>
              <div>
                <div className="text-[13.5px] font-semibold leading-tight">#{t.tag}</div>
                <div className="text-[11px] text-muted dark:text-white/55 mt-1 flex gap-2">
                  <span>{t.topic}</span><span>·</span><span>{t.posts} bài</span>
                  <span className="text-emerald-600 font-semibold">{t.delta}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className={`${GF.card} p-5`}>
          <h4 className="font-serif text-[16px] font-medium mb-3.5 flex items-center gap-2"><IF.Users size={16} className="text-emerald-500"/> Có thể bạn thích</h4>
          {DF.SUGGEST_FOLLOW.map(a => <FollowSuggestion key={a.id} author={a}/>)}
          <button className={`${GF.btn} ${GF.btnGhost} ${GF.btnSm} w-full mt-3`}>Xem thêm gợi ý</button>
        </div>

        <div className={`${GF.card} p-5`}>
          <h4 className="font-serif text-[16px] font-medium flex items-center gap-2"><IF.ChartBar size={16} className="text-emerald-500"/> Sở thích đọc của bạn</h4>
          <p className="text-[12px] text-muted dark:text-white/55 mt-1 mb-3.5">Dựa trên 30 ngày đọc gần nhất.</p>
          <div className="flex flex-col gap-3">
            {DF.TASTE.map(t => (
              <div key={t.topic}>
                <div className="flex justify-between text-[12px] mb-1">
                  <span>{t.topic}</span><span className="text-muted dark:text-white/55">{t.pct}%</span>
                </div>
                <div className="h-1 bg-ink/8 dark:bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-[#00C480] to-[#008A57] rounded-full transition-[width] duration-500 shadow-[0_0_8px_rgba(0,200,130,0.4)]" style={{ width: t.pct + '%' }}/>
                </div>
              </div>
            ))}
          </div>
          <button className={`${GF.btn} ${GF.btnGhost} ${GF.btnSm} w-full mt-3.5`}>
            <IF.Settings size={12}/> Tinh chỉnh sở thích
          </button>
        </div>

        <div className="text-center text-[12px] text-muted dark:text-white/50 leading-relaxed">
          <a href="#">Điều khoản</a> · <a href="#">Bảo mật</a> · <a href="#">Cookie</a> · <a href="#">Trợ giúp</a><br/>
          © 2026 Oecophylla
        </div>
      </aside>
    </div>
  );
}

function FollowSuggestion({ author }) {
  const [followed, setFollowed] = React.useState(false);
  return (
    <div className="flex items-center gap-2.5 py-2.5 border-t border-ink/8 dark:border-white/10 first:border-t-0">
      <Avatar author={author} size="s32" showVerified/>
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-semibold flex items-center gap-1">
          {author.name} {author.verified && <IF.Verified size={12} className="text-blue-600"/>}
        </div>
        <div className="text-[11px] text-muted dark:text-white/55">{author.reason || author.handle}</div>
      </div>
      <button onClick={() => setFollowed(!followed)}
        className={`${GF.btn} ${followed ? GF.btnGhost : GF.btnInk} ${GF.btnSm}`}>
        {followed ? 'Đang theo dõi' : '+ Theo dõi'}
      </button>
    </div>
  );
}

/* ===== Reader ===== */
function Reader({ post, onBack, toast }) {
  const [liked, setLiked] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [followed, setFollowed] = React.useState(false);
  const [commentSort, setCommentSort] = React.useState('relevant');
  if (!post) return null;
  const a = post.author;

  return (
    <div className="max-w-[720px] mx-auto px-8 py-10 pb-20" data-screen-label="05 Article Reader">
      <div className="text-[13px] text-muted dark:text-white/55 mb-4">
        <a href="#" onClick={e => { e.preventDefault(); onBack(); }} className="text-muted hover:text-ink dark:hover:text-white">
          <IF.ArrowLeft size={12} className="inline -mt-0.5"/> Quay lại bảng tin
        </a>
        {' · '}{DF.TOPICS.find(t => t.id === post.tags[0])?.name}
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <ModBadge kind={post.moderation} label={post.moderationLabel}/>
        <span className="text-[12px] text-muted dark:text-white/55"><IF.Clock size={12} className="inline -mt-0.5"/> 8 phút đọc</span>
        <span className="text-[12px] text-muted dark:text-white/55">· {post.time} · {post.stats.reads} lượt đọc</span>
      </div>

      <h1 className="font-serif text-[44px] leading-[1.08] tracking-[-0.022em] font-medium mb-4">{post.title}</h1>
      <p className="font-serif italic text-[20px] leading-[1.4] text-muted dark:text-white/65 mb-7">{post.summary}</p>

      <div className="flex items-center gap-3 my-5">
        <Avatar author={a} size="s56" showVerified/>
        <div className="flex-1">
          <div className="flex items-center gap-1.5 font-semibold">
            {a.name}
            {a.verified && <IF.Verified size={14} className="text-blue-600 dark:text-blue-400"/>}
          </div>
          <div className="text-[12px] text-muted dark:text-white/55">{a.handle} · {a.bio}</div>
        </div>
        <button onClick={() => setFollowed(!followed)}
          className={`${GF.btn} ${followed ? GF.btnGhost : GF.btnEmerald} ${GF.btnSm}`}>
          {followed ? 'Đang theo dõi' : '+ Theo dõi'}
        </button>
      </div>

      {post.image && (
        <div className="oc-ph w-full aspect-video rounded-3xl mb-7 grid place-items-center font-mono text-[10px] uppercase tracking-wider">
          ẢNH MINH HỌA · 16:9
        </div>
      )}

      <div className="font-serif text-[18.5px] leading-[1.65] text-ink-2 dark:text-white/85">
        <p className="mb-5">
          Trong sáu tháng qua, nhóm đánh giá độc lập của Đại học Bách khoa Hà Nội đã thử nghiệm 12 mô hình ngôn ngữ lớn
          phổ biến với một bộ dữ liệu kiểm thử riêng gồm 4.200 câu hội thoại có yếu tố địa phương. Kết quả khá bất ngờ.
        </p>
        <p className="mb-5">
          Lỗi không nằm ở khả năng nhận diện ký tự, mà ở việc gán ngữ nghĩa. Các từ như "mô", "tê", "răng", "rứa" thường bị
          gán sai vai trò trong câu, dẫn đến phản hồi mất ngữ cảnh.
        </p>
        <h2 className="font-serif text-[26px] mt-10 mb-3.5 tracking-tight font-medium text-ink dark:text-white">Vấn đề không chỉ là dữ liệu</h2>
        <p className="mb-5">
          Nhiều người sẽ nghĩ ngay đến chuyện thiếu dữ liệu huấn luyện. Đúng — nhưng chưa đủ. TS. Lê Minh Tuấn cho rằng phần
          lớn lỗi đến từ cách các mô hình được tinh chỉnh ưu tiên ngôn ngữ chuẩn báo chí.
        </p>
        <blockquote className="my-6 pl-6 border-l-[3px] border-emerald-500 italic text-ink dark:text-white">
          "Khi 80% dữ liệu tinh chỉnh là báo chí, chúng ta vô tình dạy mô hình rằng một số phương ngữ 'không trang trọng đủ'."
        </blockquote>
      </div>

      {/* Why card */}
      <div className="my-7 p-5 rounded-3xl bg-gradient-to-br from-emerald-500/16 to-blue-400/12 border border-white/60 dark:border-white/10 backdrop-blur-2xl shadow-glass shadow-glass-inner">
        <h4 className="font-serif text-[16px] font-medium text-emerald-700 dark:text-emerald-300 flex items-center gap-2 mb-2">
          <IF.Sparkle size={14}/> Vì sao bạn thấy bài viết này?
        </h4>
        <p className="text-[14px] text-ink-2 dark:text-white/85 leading-relaxed mb-3">
          Bạn đã đọc 11 bài về AI trong 30 ngày qua và tương tác nhiều với chủ đề <b>"AI có trách nhiệm"</b>.
          Bài viết này có nguồn được xác minh, độ tin cậy cao và đang nhận phản hồi tích cực từ cộng đồng bạn theo dõi.
        </p>
        <div className="flex flex-wrap gap-1.5">
          <span className={`${GF.chip} ${GF.chipActive}`}>AI có trách nhiệm</span>
          <span className={`${GF.chip} ${GF.chipActive}`}>Khoa học dữ liệu</span>
          <span className={`${GF.chip} ${GF.chipOutline}`}>Tiếng Việt tự nhiên</span>
        </div>
      </div>

      <div className="flex gap-1.5 my-8 py-3.5 border-y border-ink/8 dark:border-white/10 flex-wrap">
        <ActionButton active={liked} onClick={() => { setLiked(!liked); toast(liked ? 'Đã bỏ thích.' : 'Đã thích.'); }}
          icon={liked ? <IF.HeartFill size={16}/> : <IF.Heart size={16}/>}
          activeClass="text-rose-600 bg-rose-500/12">
          {post.stats.likes + (liked ? 1 : 0)} lượt thích
        </ActionButton>
        <ActionButton icon={<IF.Comment size={16}/>}>{post.stats.comments} bình luận</ActionButton>
        <ActionButton icon={<IF.Share size={16}/>}>Chia sẻ</ActionButton>
        <ActionButton active={saved} onClick={() => { setSaved(!saved); toast(saved ? 'Đã bỏ lưu.' : 'Đã lưu.'); }}
          icon={saved ? <IF.BookmarkFill size={16}/> : <IF.Bookmark size={16}/>}
          activeClass="text-emerald-600 bg-emerald-500/15">
          {saved ? 'Đã lưu' : 'Lưu'}
        </ActionButton>
        <span className="flex-1"/>
        <ActionButton icon={<IF.Flag size={16}/>}>Báo cáo</ActionButton>
      </div>

      {/* Comments */}
      <div className="flex items-baseline justify-between mt-8 mb-3">
        <h3 className="font-serif text-[22px] font-medium tracking-tight">{post.stats.comments} bình luận</h3>
        <div className="flex gap-1">
          <button onClick={() => setCommentSort('relevant')} className={`${GF.btn} ${commentSort === 'relevant' ? GF.btnInk : GF.btnSoft} ${GF.btnSm}`}>Liên quan nhất</button>
          <button onClick={() => setCommentSort('new')} className={`${GF.btn} ${commentSort === 'new' ? GF.btnInk : GF.btnSoft} ${GF.btnSm}`}>Mới nhất</button>
        </div>
      </div>

      <div className={`${GF.card} p-4 mb-6 flex gap-3`}>
        <Avatar author={DF.AUTHORS[0]} size="s40"/>
        <div className="flex-1">
          <textarea rows={2} placeholder="Viết bình luận của bạn… (lịch sự, có dẫn chứng nếu có thể)"
            className="w-full bg-transparent resize-none text-[14px] outline-none placeholder:text-muted"/>
          <div className="flex items-center pt-2.5 mt-2 border-t border-ink/8 dark:border-white/10">
            <span className="text-[12px] text-muted dark:text-white/55">
              Bình luận sẽ hiển thị công khai. Hành vi quấy rối sẽ bị ẩn tự động.
            </span>
            <button className={`${GF.btn} ${GF.btnEmerald} ${GF.btnSm} ml-auto`}>Đăng bình luận</button>
          </div>
        </div>
      </div>

      <CommentItem author={DF.AUTHORS[3]} time="12 phút trước"
        body="Bài viết phân tích cân bằng. Một câu hỏi: nhóm có thử kiểm tra với fine-tuning bằng dữ liệu cộng đồng (như crowdsourcing) chưa? Có thể bù lệch nhanh hơn là chờ data sạch."
        replies={[{ author: DF.AUTHORS[0], time: '8 phút', body: 'Có anh ạ, bọn em đã thử với 4 mô hình. Cải thiện 8–11%. Đang viết phần 2.' }]}/>
      <CommentItem author={DF.AUTHORS[5]} time="40 phút trước"
        body="'Báo chí chuẩn' không có lỗi gì, nhưng nếu trở thành tiêu chuẩn duy nhất cho fine-tuning thì đúng là vấn đề."/>

      {/* Related */}
      <h3 className="font-serif text-[22px] font-medium tracking-tight mt-10 mb-3">Bài viết liên quan</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {DF.POSTS.slice(1, 3).map(p => (
          <div key={p.id} onClick={onBack} className={`${GF.card} p-5 cursor-pointer transition-all hover:-translate-y-0.5`}>
            <div className={GF.eyebrow + ' mb-1.5'}>{DF.TOPICS.find(t => t.id === p.tags[0])?.name}</div>
            <div className="font-serif text-[17px] tracking-tight leading-snug mb-2">{p.title}</div>
            <div className="text-[12px] text-muted dark:text-white/55">{p.author.name} · {p.time}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CommentItem({ author, time, body, replies = [] }) {
  return (
    <div className="flex gap-3 py-5 border-t border-ink/8 dark:border-white/10">
      <Avatar author={author} size="s40" showVerified/>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="font-semibold text-[13px]">{author.name}</span>
          <span className="text-[11px] text-muted dark:text-white/55">{time}</span>
        </div>
        <div className="text-[14px] text-ink-2 dark:text-white/85 leading-relaxed mt-1 mb-2">{body}</div>
        <div className="flex gap-1 text-[12px]">
          <button className="px-2 py-1 rounded text-muted hover:text-ink dark:hover:text-white hover:bg-white/50"><IF.Heart size={12} className="inline -mt-0.5 mr-1"/>8</button>
          <button className="px-2 py-1 rounded text-muted hover:text-ink dark:hover:text-white hover:bg-white/50">Trả lời</button>
          <button className="px-2 py-1 rounded text-muted hover:text-ink dark:hover:text-white hover:bg-white/50">Báo cáo</button>
        </div>
        {replies.length > 0 && (
          <div className="mt-2 pl-4 border-l border-ink/10 dark:border-white/10">
            {replies.map((r, i) => (
              <div key={i} className="flex gap-3 py-3">
                <Avatar author={r.author} size="s32"/>
                <div>
                  <div className="flex items-baseline gap-2">
                    <span className="font-semibold text-[13px]">{r.author.name}</span>
                    <span className="text-[11px] text-muted dark:text-white/55">{r.time}</span>
                  </div>
                  <div className="text-[14px] text-ink-2 dark:text-white/85 leading-relaxed mt-1">{r.body}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { Feed, Reader });

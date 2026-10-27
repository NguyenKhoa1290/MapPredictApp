import { Link } from 'react-router';
import { usePublicData } from '../app/PublicData';
import { ProjectCards } from '../shared/ui/ProjectCards';

export function About() {
  const { content, projects } = usePublicData();
  if (!content) return null;
  return <>
    <section className="hero container" aria-labelledby="hero-title"><div className="hero-copy">
      <p className="eyebrow"><span /> Dữ liệu và không gian quy hoạch</p>
      <h1 id="hero-title">Hiểu không gian<br /><em>Nhìn rõ tiềm năng</em></h1>
      <p className="hero-description">Kết nối AI, dữ liệu và bản đồ để đánh giá quỹ đất theo quy hoạch chi tiết</p>
      <div className="button-row"><Link className="button primary" to="/assessment">Đi đến công cụ đánh giá <span aria-hidden="true">↗</span></Link><Link className="button secondary" to="/projects">Khám phá dự án</Link></div>
      <div className="hero-footnote"><span className="mini-grid" aria-hidden="true">▦</span><span>Từ dữ liệu ô đất đến góc nhìn tổng thể</span></div>
    </div><figure className="hero-figure"><div className="figure-heading"><span><i /> GÓC NHÌN KHÔNG GIAN</span></div><div className="hero-map"><img src="/static/image/hero.jpg" alt="Không gian quy hoạch" fetchPriority="high" /></div></figure></section>
    <section className="intro-section container" aria-labelledby="intro-title"><p className="eyebrow section-kicker">01 Giới thiệu</p><div className="intro-content"><h2 id="intro-title">Một cách tiếp cận<br />quy hoạch bằng dữ liệu</h2><div className="intro-prose">{content.intro.split(/\n\s*\n/).filter(paragraph => paragraph.trim()).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div></div></section>
    <section className="vision-section" aria-labelledby="vision-title"><div className="container"><div className="section-heading"><div><p className="eyebrow">02 Tầm nhìn</p><h2 id="vision-title">Ba định hướng<br />Một góc nhìn xuyên suốt</h2></div></div><div className="vision-grid">{content.visions.map((vision, index) => <article key={vision.title}><span className="vision-number">0{index + 1}</span><h3>{vision.title}</h3><p>{vision.description}</p></article>)}</div></div></section>
    <section className="projects-section container" aria-labelledby="about-projects-title"><div className="section-heading"><div><p className="eyebrow">03 Dự án</p><h2 id="about-projects-title">Từ nghiên cứu<br />đến ứng dụng</h2></div><Link className="text-link" to="/projects">Khám phá dự án</Link></div><ProjectCards projects={projects} /></section>
    <section className="team-section" aria-labelledby="team-title"><div className="container"><div className="section-heading"><div><p className="eyebrow">04 Nhóm thực hiện</p><h2 id="team-title">Những người<br />cùng xây dựng</h2></div></div><div className="team-grid">{content.members.map((member, index) => <article className="team-card" key={member.id}><div className="portrait"><img src={`/static/image/${member.id}.jpg`} alt={member.name || `Thành viên ${index + 1}`} loading="lazy" /></div><h3>{member.name || `Thành viên 0${index + 1}`}</h3>{member.role && <p>{member.role}</p>}{member.bio && <p className="member-bio">{member.bio}</p>}{member.contact && <span className="contact-placeholder">{member.contact}</span>}</article>)}</div></div></section>
    <section className="closing-section container"><div><p className="eyebrow">BẮT ĐẦU KHÁM PHÁ</p><h2>Đưa dữ liệu của bạn<br />vào một góc nhìn mới</h2></div><Link className="button primary" to="/assessment">Đi đến công cụ đánh giá</Link></section>
  </>;
}

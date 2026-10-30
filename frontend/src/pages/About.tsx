import { Link } from 'react-router';
import { usePublicData } from '../app/PublicData';
import { ProjectCards } from '../shared/ui/ProjectCards';

export function About() {
  const { content, projects } = usePublicData();
  if (!content) return null;
  return <>
    <section className="gp-hero" aria-labelledby="hero-title">
      <div className="container gp-hero-grid">
        <div className="gp-hero-copy">
          <p className="gp-kicker"><span /> GEOPLAN AI <span className="gp-kicker-divider" /> DỮ LIỆU & KHÔNG GIAN</p>
          <h1 id="hero-title">Hiểu không gian<br /><em>Nhìn rõ tiềm năng</em></h1>
          <p className="gp-hero-description">Kết nối AI, dữ liệu và bản đồ để đánh giá quỹ đất theo quy hoạch chi tiết</p>
          <div className="button-row gp-hero-actions">
            <Link className="button primary" to="/assessment">Đi đến công cụ đánh giá <span aria-hidden="true">→</span></Link>
            <Link className="button secondary" to="/projects">Khám phá dự án</Link>
          </div>
          <p className="gp-hero-note">Từ dữ liệu ô đất đến góc nhìn tổng thể</p>
        </div>
        <figure className="gp-hero-figure">
          <img src="/static/image/hero.jpg?v=7214ea63" alt="Minh họa không gian quy hoạch với sông, đô thị và các lớp dữ liệu đất đai" fetchPriority="high" />
          <figcaption><span><i /> GÓC NHÌN KHÔNG GIAN</span><span>QUY HOẠCH CHI TIẾT</span></figcaption>
        </figure>
      </div>
      <div className="container gp-hero-bottom"><span>KHÔNG GIAN</span><span>DỮ LIỆU</span><span>ỨNG DỤNG AI</span><span className="gp-bottom-caption">Góc nhìn mới cho quy hoạch</span></div>
    </section>

    <section className="container gp-intro" aria-labelledby="intro-title">
      <div className="gp-section-label"><p className="gp-section-overline">01 / GIỚI THIỆU</p></div>
      <div className="gp-intro-content">
        <div><p className="gp-section-overline">DỮ LIỆU TẠO NÊN GÓC NHÌN</p><h2 id="intro-title">Một cách tiếp cận<br />quy hoạch bằng dữ liệu</h2></div>
        <div className="intro-prose">{content.intro.split(/\n\s*\n/).filter(paragraph => paragraph.trim()).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>
      </div>
    </section>

    <section className="gp-vision" aria-labelledby="vision-title"><div className="container">
      <div className="gp-section-heading"><div><p className="gp-section-overline">02 / TẦM NHÌN</p><h2 id="vision-title">Ba định hướng<br />Một góc nhìn xuyên suốt</h2></div><p><br /></p></div>
      <div className="gp-vision-grid">{content.visions.map((vision, index) => <article key={vision.title}>
        <div className="gp-vision-top"><span>0{index + 1}</span><span aria-hidden="true"></span></div>
        <h3>{vision.title}</h3><p>{vision.description}</p>
      </article>)}</div>
    </div></section>

    <section className="container gp-projects" aria-labelledby="about-projects-title">
      <div className="gp-section-heading"><div><p className="gp-section-overline">03 / DỰ ÁN</p><h2 id="about-projects-title">Từ nghiên cứu<br />đến ứng dụng</h2></div><Link className="text-link" to="/projects">Khám phá dự án <span aria-hidden="true">→</span></Link></div>
      <ProjectCards projects={projects} />
    </section>

    {/* <section className="team-section" aria-labelledby="team-title"><div className="container"><div className="section-heading"><div><p className="eyebrow">04 Nhóm thực hiện</p><h2 id="team-title">Những người<br />cùng xây dựng</h2></div></div><div className="team-grid">{content.members.map((member, index) => <article className="team-card" key={member.id}><div className="portrait"><img src={`/static/image/${member.id}.jpg`} alt={member.name || `Thành viên ${index + 1}`} loading="lazy" /></div><h3>{member.name || `Thành viên 0${index + 1}`}</h3>{member.role && <p>{member.role}</p>}{member.bio && <p className="member-bio">{member.bio}</p>}{member.contact && <span className="contact-placeholder">{member.contact}</span>}</article>)}</div></div></section> */}

    <section className="gp-closing" aria-labelledby="closing-title"><div className="container gp-closing-inner">
      <div><p className="gp-section-overline">BẮT ĐẦU KHÁM PHÁ</p><h2 id="closing-title">Đưa dữ liệu của bạn<br />vào một góc nhìn mới</h2><p>Khám phá không gian và kết quả đánh giá theo cách trực quan hơn</p></div>
      <Link className="button gp-closing-button" to="/assessment">Đi đến công cụ đánh giá <span aria-hidden="true">→</span></Link>
    </div></section>
  </>;
}

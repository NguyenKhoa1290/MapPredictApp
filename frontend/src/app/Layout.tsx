import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router';
import { usePublicData } from './PublicData';
import { Assessment } from '../pages/Assessment';

export function Layout() {
  const { loading, error, retry, content } = usePublicData();
  const { pathname } = useLocation();
  const isAssessment = pathname.replace(/\/$/, '') === '/assessment';
  const [assessmentMounted, setAssessmentMounted] = useState(isAssessment);
  useEffect(() => { if (isAssessment) setAssessmentMounted(true); }, [isAssessment]);
  const main = useRef<HTMLElement>(null);
  const header = useRef<HTMLElement>(null);
  const initial = useRef(true);
  useLayoutEffect(() => {
    const element = header.current;
    if (!element) return;
    const style = document.documentElement.style;
    const previous = style.getPropertyValue('--site-header-height');
    const measure = () => {
      const height = element.getBoundingClientRect().height;
      if (height > 0) style.setProperty('--site-header-height', `${height}px`);
    };
    measure();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    observer?.observe(element);
    window.addEventListener('resize', measure);
    return () => {
      observer?.disconnect(); window.removeEventListener('resize', measure);
      if (previous) style.setProperty('--site-header-height', previous);
      else style.removeProperty('--site-header-height');
    };
  }, []);
  useEffect(() => {
    document.title = `${pathname.includes('/projects') ? 'Dự án' : pathname.startsWith('/assessment') ? 'Đánh giá quỹ đất' : 'Giới thiệu'} | Quỹ đất`;
    if (initial.current) { initial.current = false; return; }
    window.scrollTo({ top: 0, behavior: 'instant' });
    main.current?.focus({ preventScroll: true });
  }, [pathname]);
  return <>
    <a className="skip-link" href="#main">Đến nội dung chính</a>
    <header className="site-header" ref={header}>
      <Link className="brand" to="/" aria-label="Quỹ đất | Trang giới thiệu">
        <svg width="35" height="35" viewBox="0 0 36 36" aria-hidden="true"><path d="m18 2 15 8.5v15L18 34 3 25.5v-15Z" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="m3 10.5 15 9 15-9M18 19.5V34M10.5 6.25l15 9v14M3 18l15 9 15-9" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
        <span>{content?.brand || 'Quỹ đất'}<small>NGHIÊN CỨU & ỨNG DỤNG</small></span>
      </Link>
      <nav aria-label="Điều hướng chính"><NavLink to="/" end>Giới thiệu</NavLink><NavLink to="/projects">Dự án</NavLink><NavLink to="/assessment">Đánh giá quỹ đất <span aria-hidden="true">↗</span></NavLink></nav>
    </header>
    <main id="main" ref={main} tabIndex={-1}>
      {loading ? <div className="portal-state container" role="status">Đang tải nội dung…</div>
        : error ? <div className="portal-state container" role="alert"><h1>Chưa tải được nội dung</h1><p>{error}</p><button type="button" className="button primary" onClick={retry}>Thử lại</button></div>
        : <>
          {assessmentMounted || isAssessment ? <div hidden={!isAssessment}><Assessment active={isAssessment} /></div> : null}
          {!isAssessment ? <Outlet /> : null}
        </>}
    </main>
    <footer className="site-footer"><div className="container footer-content"><Link className="footer-brand" to="/">Quỹ đất<span>NGHIÊN CỨU & ỨNG DỤNG</span></Link><Link className="text-link" to="/"><span aria-hidden="true">←</span> Về trang giới thiệu</Link></div></footer>
  </>;
}

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router';
import { usePublicData } from './PublicData';
import { Assessment } from '../pages/Assessment';

export function Layout() {
  const { loading, error, retry, content } = usePublicData();
  const brandName = content?.brand || 'GeoPlan AI';
  const brandWordmark = brandName === 'GeoPlan AI'
    ? <>GeoPlan <em className="brand-wordmark-ai">AI</em></>
    : brandName;
  const { pathname } = useLocation();
  const adminHost = window.location.hostname === 'admin.danhgiaquyhoach.top';
  const publicPath = (path: string) => adminHost ? 'https://danhgiaquyhoach.top/portal' + path : path;
  const isAssessment = pathname.replace(/\/$/, '') === '/assessment';
  const hideChrome = /^\/projects\/[^/]+\/?$/.test(pathname) || /^\/assessment(?:\/|$)/.test(pathname);
  const [assessmentMounted, setAssessmentMounted] = useState(isAssessment);
  useEffect(() => { if (isAssessment) setAssessmentMounted(true); }, [isAssessment]);
  const main = useRef<HTMLElement>(null);
  const header = useRef<HTMLElement>(null);
  const initial = useRef(true);
  useLayoutEffect(() => {
    const element = header.current;
    const style = document.documentElement.style;
    const previous = style.getPropertyValue('--site-header-height');
    const restore = () => {
      if (previous) style.setProperty('--site-header-height', previous);
      else style.removeProperty('--site-header-height');
    };
    if (!element) { style.setProperty('--site-header-height', '0px'); return restore; }
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
      restore();
    };
  }, [hideChrome]);
  useEffect(() => {
    document.title = `${pathname.startsWith('/admin') ? 'Quản trị AI' : pathname.includes('/projects') ? 'Dự án' : pathname.startsWith('/assessment') ? 'Đánh giá quỹ đất' : 'Giới thiệu'} | GeoPlan AI`;
    if (initial.current) { initial.current = false; return; }
    window.scrollTo({ top: 0, behavior: 'instant' });
    main.current?.focus({ preventScroll: true });
  }, [pathname]);
  return <>
    <a className="skip-link" href="#main">Đến nội dung chính</a>
    {!hideChrome ? <header className="site-header" ref={header}>
      <Link className="brand" to={publicPath('/')} reloadDocument={adminHost} aria-label="GeoPlan AI | Trang giới thiệu">
        <span className="brand-mark" aria-hidden="true"><img src="/static/image/logo%201.png" alt="" /></span>
        <span><strong className="brand-wordmark">{brandWordmark}</strong><small>QUY HOẠCH & DỮ LIỆU KHÔNG GIAN</small></span>
      </Link>
      <nav aria-label="Điều hướng chính"><NavLink to={publicPath('/')} reloadDocument={adminHost} end>Giới thiệu</NavLink><NavLink to={publicPath('/projects')} reloadDocument={adminHost}>Dự án</NavLink><NavLink to={publicPath('/assessment')} reloadDocument={adminHost}>Đánh giá quỹ đất <span aria-hidden="true">↗</span></NavLink></nav>
    </header> : null}
    <main id="main" ref={main} tabIndex={-1}>
      {loading ? <div className="portal-state container" role="status">Đang tải nội dung…</div>
        : error ? <div className="portal-state container" role="alert"><h1>Chưa tải được nội dung</h1><p>{error}</p><button type="button" className="button primary" onClick={retry}>Thử lại</button></div>
        : <>
          {assessmentMounted || isAssessment ? <div hidden={!isAssessment}><Assessment active={isAssessment} /></div> : null}
          {!isAssessment ? <Outlet /> : null}
        </>}
    </main>
    {!hideChrome ? <footer className="site-footer"><div className="container footer-content"><Link className="footer-brand" to={publicPath('/')} reloadDocument={adminHost} aria-label="GeoPlan AI | Trang giới thiệu"><span className="brand-mark brand-mark--dark" aria-hidden="true"><img src="/static/image/logo%202.png" alt="" /></span><span className="footer-brand-copy"><strong className="brand-wordmark">{brandWordmark}</strong><small>QUY HOẠCH & DỮ LIỆU KHÔNG GIAN</small></span></Link><Link className="text-link" to={publicPath('/')} reloadDocument={adminHost}><span aria-hidden="true">←</span> Về trang giới thiệu</Link></div></footer> : null}
  </>;
}

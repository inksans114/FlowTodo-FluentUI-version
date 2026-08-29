import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import * as THREE from 'three';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import {
  ArrowDown, ArrowRight, BarChart3, Blocks, Check, CheckCircle2,
  ChevronRight, Clock3, Download, Focus, Layers3,
  ListChecks, Menu, Minus, Play, Sparkles, X,
} from 'lucide-react';
import './styles.css';

gsap.registerPlugin(ScrollTrigger);

const GITHUB_LINK = 'https://github.com/inksans114/FlowTodo-FluentUI-version';
const DOWNLOAD_LINK = `${GITHUB_LINK}/releases`;

function FlowMark() {
  return <span className="flow-mark" aria-hidden="true"><i /><i /><i /><i /></span>;
}

function GithubMark() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C6.48 2 2 6.59 2 12.25c0 4.53 2.87 8.37 6.84 9.72.5.1.68-.22.68-.49v-1.9c-2.78.62-3.37-1.21-3.37-1.21-.45-1.19-1.11-1.5-1.11-1.5-.91-.64.07-.62.07-.62 1 .08 1.53 1.06 1.53 1.06.9 1.57 2.35 1.12 2.92.86.09-.66.35-1.12.64-1.37-2.22-.26-4.56-1.14-4.56-5.07 0-1.12.39-2.04 1.03-2.76-.1-.26-.45-1.31.1-2.72 0 0 .84-.28 2.75 1.05A9.34 9.34 0 0 1 12 6.96a9.3 9.3 0 0 1 2.5.35c1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.46.1 2.72.64.72 1.03 1.64 1.03 2.76 0 3.94-2.34 4.8-4.57 5.06.36.32.68.94.68 1.9v2.82c0 .27.18.59.69.49A10.25 10.25 0 0 0 22 12.25C22 6.59 17.52 2 12 2Z" fill="currentColor" stroke="none" /></svg>;
}

function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="site-header">
      <a className="brand" href="#top" aria-label="FlowTodo 首页"><FlowMark /><span>FlowTodo</span></a>
      <button className="icon-button menu-button" onClick={() => setOpen(!open)} aria-label="打开导航">
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>
      <nav className={open ? 'nav-open' : ''} onClick={() => setOpen(false)}>
        <a href="#workflow">任务流</a><a href="#focus">专注</a><a href="#details">细节</a>
        <a href={GITHUB_LINK}>GitHub</a>
        <a className="nav-download" href={DOWNLOAD_LINK}><Download size={16} /> 下载</a>
      </nav>
    </header>
  );
}

function FlowScene() {
  const mountRef = useRef(null);
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(0.2, 0.2, 9.2);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.7));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    group.rotation.set(-0.12, -0.42, -0.05);
    scene.add(group);
    const colors = [0x0f6cbd, 0x4f6bed, 0x7a67d8, 0x20a46b];
    const cards = [];
    for (let i = 0; i < 5; i += 1) {
      const card = new THREE.Mesh(
        new THREE.BoxGeometry(3.6, 0.72, 0.08),
        new THREE.MeshPhysicalMaterial({
          color: i === 2 ? colors[1] : 0xffffff,
          roughness: 0.2, transmission: i === 2 ? 0.02 : 0.12,
          transparent: true, opacity: i === 2 ? 0.95 : 0.82, clearcoat: 1,
        }),
      );
      card.position.set((i % 2) * 0.38 - 0.2, 1.55 - i * 0.8, i * -0.34);
      card.rotation.z = (i % 2 ? 1 : -1) * 0.035;
      group.add(card); cards.push(card);
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.105, 22, 22),
        new THREE.MeshStandardMaterial({ color: i === 2 ? 0xffffff : colors[i % colors.length], roughness: 0.28 }),
      );
      dot.position.set(card.position.x - 1.35, card.position.y, card.position.z + 0.08);
      group.add(dot);
    }
    const rail = new THREE.Mesh(
      new THREE.CylinderGeometry(0.018, 0.018, 4.2, 12),
      new THREE.MeshStandardMaterial({ color: 0x9aa5b1, transparent: true, opacity: 0.4 }),
    );
    rail.position.set(-1.55, -0.05, 0.12); group.add(rail);
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(2.85, 0.018, 10, 120),
      new THREE.MeshBasicMaterial({ color: 0x0f6cbd, transparent: true, opacity: 0.18 }),
    );
    ring.rotation.x = Math.PI / 2.3; ring.position.z = -1.5; group.add(ring);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xdce5ef, 2.5));
    const key = new THREE.DirectionalLight(0xffffff, 4.5); key.position.set(4, 5, 7); scene.add(key);
    const blue = new THREE.PointLight(0x0f6cbd, 16, 14); blue.position.set(-3, -1, 4); scene.add(blue);

    let mouseX = 0; let mouseY = 0;
    const onPointer = (event) => {
      mouseX = (event.clientX / window.innerWidth - 0.5) * 0.28;
      mouseY = (event.clientY / window.innerHeight - 0.5) * 0.2;
    };
    const resize = () => {
      renderer.setSize(mount.clientWidth, mount.clientHeight, false);
      camera.aspect = mount.clientWidth / mount.clientHeight; camera.updateProjectionMatrix();
    };
    window.addEventListener('resize', resize); window.addEventListener('pointermove', onPointer, { passive: true }); resize();
    const timer = new THREE.Timer();
    timer.connect(document); let frame;
    const draw = () => {
      timer.update();
      const elapsed = timer.getElapsed();
      if (!reduceMotion) {
        group.rotation.y += (mouseX - group.rotation.y - 0.42) * 0.025;
        group.rotation.x += (-mouseY - group.rotation.x - 0.12) * 0.025;
        group.position.y = Math.sin(elapsed * 0.65) * 0.08;
        ring.rotation.z = elapsed * 0.08;
      }
      renderer.render(scene, camera); frame = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(frame); window.removeEventListener('resize', resize); window.removeEventListener('pointermove', onPointer);
      timer.disconnect();
      scene.traverse((child) => { child.geometry?.dispose(); child.material?.dispose(); });
      renderer.dispose(); renderer.domElement.remove();
    };
  }, []);
  return <div className="flow-scene" ref={mountRef} aria-hidden="true" />;
}

function ScreenshotSlot({ src, label, children, className = '' }) {
  const [loaded, setLoaded] = useState(false);
  return (
    <div className={`screenshot-shell ${className}`}>
      <div className="window-bar">
        <span className="window-title"><FlowMark /> FlowTodo</span>
        <span className="window-controls"><Minus /><span className="window-square" /><X /></span>
      </div>
      <div className="screenshot-body">
        {!loaded && children}
        <img className={loaded ? 'is-loaded' : ''} src={src} alt={label} onLoad={() => setLoaded(true)} onError={() => setLoaded(false)} />
        {!loaded && <span className="slot-label">图片位置 · {label}</span>}
      </div>
    </div>
  );
}

function HeroMock() {
  return (
    <div className="mock-app">
      <aside className="mock-sidebar">
        <div className="mock-side-brand"><FlowMark /><strong>FlowTodo</strong></div>
        {[[CheckCircle2, '今日任务', true], [Layers3, '任务流'], [Blocks, '项目'], [Focus, '专注模式'], [Sparkles, 'AI 规划']].map(([Icon, text, active]) => (
          <div className={active ? 'mock-nav active' : 'mock-nav'} key={text}><Icon />{text}</div>
        ))}
      </aside>
      <main className="mock-main">
        <div className="mock-eyebrow">8 月 20 日 · 星期四</div>
        <div className="mock-heading-row"><h3>早上好，今日任务</h3><button><span>+</span> 添加任务</button></div>
        <div className="metric-row"><div><span>待完成</span><strong>5</strong></div><div><span>今日完成</span><strong>3</strong></div><div><span>今日专注</span><strong>48 <small>分钟</small></strong></div></div>
        <div className="mock-list-title"><strong>接下来</strong><span>5 项</span></div>
        <div className="task-row checked"><i><Check /></i><span><b>整理发布页文案</b><small>FlowTodo 1.0</small></span><em>已完成</em></div>
        <div className="task-row"><i /><span><b>完成视觉细节检查</b><small>今天 · 11:30</small></span><button><Play /> 专注</button></div>
        <div className="task-row"><i /><span><b>准备首个公开版本</b><small>发布计划</small></span><button><Play /> 专注</button></div>
      </main>
    </div>
  );
}

function FocusMock() {
  return (
    <div className="focus-mock">
      <div className="focus-top"><span>专注会话</span><span>阶段 1 / 3</span></div>
      <div className="focus-center"><span className="focus-kicker">正在专注</span><strong>24:18</strong><h4>完成视觉细节检查</h4><div className="focus-progress"><i /></div><div className="focus-actions"><button><span>Ⅱ</span> 暂停</button><button className="quiet">结束</button></div></div>
      <div className="island-mini"><i /><span>24:18</span><small>专注中</small></div>
    </div>
  );
}

function ProjectMock() {
  const items = [['FlowTodo 1.0', '产品发布', 78], ['个人知识库', '长期项目', 42], ['九月阅读计划', '日常成长', 18]];
  return (
    <div className="project-mock">
      <div className="project-head"><span><small>工作区</small><strong>所有项目</strong></span><button>+ 新建项目</button></div>
      {items.map(([name, meta, progress]) => <div className="project-row" key={name}><div className="project-icon"><Blocks /></div><span><strong>{name}</strong><small>{meta}</small></span><div className="project-bar"><i style={{ width: `${progress}%` }} /></div><em>{progress}%</em><ChevronRight /></div>)}
    </div>
  );
}

function Reveal({ children, className = '' }) {
  const ref = useRef(null);
  useEffect(() => {
    const animation = gsap.fromTo(ref.current, { y: 34, opacity: 0 }, { y: 0, opacity: 1, duration: 0.85, ease: 'power3.out', scrollTrigger: { trigger: ref.current, start: 'top 86%', once: true } });
    return () => animation.kill();
  }, []);
  return <div ref={ref} className={className}>{children}</div>;
}

function App() {
  const heroRef = useRef(null);
  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.hero-copy > *', { y: 28, opacity: 0, duration: 0.9, stagger: 0.1, ease: 'power3.out' });
      gsap.from('.hero-product', { y: 56, opacity: 0, scale: 0.985, duration: 1.1, delay: 0.25, ease: 'power3.out' });
      gsap.to('.hero-product', { yPercent: -6, ease: 'none', scrollTrigger: { trigger: heroRef.current, start: 'top top', end: 'bottom top', scrub: 0.7 } });
    }, heroRef);
    return () => ctx.revert();
  }, []);
  return (
    <>
      <Header />
      <main id="top">
        <section className="hero" ref={heroRef}>
          <FlowScene />
          <div className="hero-copy">
            <p className="product-label"><span>Windows 原生效率工具</span><i />FlowTodo 1.0</p>
            <h1>把一天，排成一条<br />清晰的路。</h1>
            <p className="hero-lead">任务、项目与专注在同一个安静的工作区里自然衔接。少一点来回切换，多一点真正完成。</p>
            <div className="hero-actions"><a className="primary-button" href={DOWNLOAD_LINK}><Download /> 下载 Windows 版</a><a className="text-button" href="#workflow">看看它怎么工作 <ArrowDown /></a></div>
            <p className="hero-note">Windows 10 / 11 · 本地数据 · 开源发布</p>
          </div>
          <div className="hero-product"><ScreenshotSlot src="/screenshots/hero.webp" label="主界面 hero.webp" className="hero-shot"><HeroMock /></ScreenshotSlot></div>
        </section>

        <section className="statement" id="workflow">
          <Reveal><p className="section-index">01 / 一条连贯的工作流</p><h2>待办不该只是<br />一张越来越长的清单。</h2></Reveal>
          <Reveal className="statement-copy"><p>FlowTodo 把零散任务组织成可以启动、推进、完成的流程。普通待办适合今天，任务流适合重复步骤，项目则照看更长的目标。</p><a href="#focus">继续了解 <ArrowRight /></a></Reveal>
        </section>

        <section className="feature-band feature-projects"><div className="band-inner">
          <Reveal className="feature-copy"><span className="feature-number">01</span><div className="icon-title"><Layers3 /><span>任务流与项目</span></div><h2>从下一步开始，<br />而不是从压力开始。</h2><p>把复杂目标拆成清晰里程碑。启动前先确认步骤，进行中只关注眼前这一项。</p><ul><li><Check /> 今日任务与每日重复任务</li><li><Check /> 可复用的多阶段任务流</li><li><Check /> 带进度的长期项目</li></ul></Reveal>
          <Reveal className="feature-visual"><ScreenshotSlot src="/screenshots/projects.webp" label="项目界面 projects.webp"><ProjectMock /></ScreenshotSlot></Reveal>
        </div></section>

        <section className="feature-band focus-band" id="focus"><div className="band-inner reverse">
          <Reveal className="feature-visual focus-visual"><ScreenshotSlot src="/screenshots/focus.webp" label="专注界面 focus.webp"><FocusMock /></ScreenshotSlot></Reveal>
          <Reveal className="feature-copy light-copy"><span className="feature-number">02</span><div className="icon-title"><Clock3 /><span>专注模式</span></div><h2>开始以后，<br />只留下正在做的事。</h2><p>倒计时、阶段和当前任务保持同步。桌面灵动岛让进度始终可见，又不会打断注意力。</p><div className="focus-stat"><strong>25:00</strong><span>默认专注时长<br />可随工作节奏调整</span></div></Reveal>
        </div></section>

        <section className="detail-section" id="details">
          <Reveal className="detail-heading"><p className="section-index">03 / 安静，但不简单</p><h2>需要的能力都在。<br />不需要时，它们退到后面。</h2></Reveal>
          <div className="detail-grid">
            <Reveal className="detail-item"><Sparkles /><span>AI 规划</span><h3>把模糊想法整理成可执行步骤</h3><p>预览长期计划，再决定是否加入你的工作区。</p></Reveal>
            <Reveal className="detail-item"><BarChart3 /><span>账户统计</span><h3>看见时间真正花在了哪里</h3><p>完成数与专注时间清晰记录，不制造无意义的排名。</p></Reveal>
            <Reveal className="detail-item"><ListChecks /><span>桌面组件</span><h3>重要任务离桌面更近一步</h3><p>无需打开主窗口，也能快速查看今天和进入专注。</p></Reveal>
          </div>
          <Reveal className="wide-shot-wrap"><ScreenshotSlot src="/screenshots/details.webp" label="功能全景 details.webp"><div className="details-placeholder"><div className="detail-side"><FlowMark /><span /><span /><span /><span /></div><div className="detail-columns"><div /><div /><div /></div><div className="detail-chart"><i /><i /><i /><i /><i /><i /><i /></div></div></ScreenshotSlot></Reveal>
        </section>

        <section className="native-section">
          <Reveal className="native-copy"><p className="section-index">为 Windows 而生</p><h2>熟悉的设计，<br />原生的速度。</h2><p>基于 PySide6、QML 与 RinUI 构建。跟随系统明暗模式，支持窗口材质与强调色，数据保存在本地。</p></Reveal>
          <div className="native-list"><Reveal><span>01</span><strong>Fluent Design</strong><small>与 Windows 11 保持一致的视觉语言</small></Reveal><Reveal><span>02</span><strong>本地优先</strong><small>已有 JSON 数据无需转换，继续掌握自己的数据</small></Reveal><Reveal><span>03</span><strong>开源</strong><small>功能与实现都可以被检查、修改和延伸</small></Reveal></div>
        </section>

        <section className="download-section" id="download"><div className="download-lines" aria-hidden="true"><i /><i /><i /><i /></div><Reveal className="download-content"><FlowMark /><p>FlowTodo 1.0</p><h2>把今天真正完成。</h2><p className="download-sub">适用于 Windows 10 与 Windows 11</p><div className="download-actions"><a className="primary-button light" href={DOWNLOAD_LINK}><Download /> 下载 Windows 版</a><a className="outline-button" href={GITHUB_LINK}><GithubMark /> 查看源代码</a></div></Reveal></section>
      </main>
      <footer><a className="brand" href="#top"><FlowMark /><span>FlowTodo</span></a><p>把任务变成流动的进展。</p><span>© 2026 FlowTodo</span></footer>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);

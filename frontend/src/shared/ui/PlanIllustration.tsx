/** Deliberately schematic artwork, never geographic source data or prediction output. */
export function PlanIllustration({ variant = 0, dark = false }: { variant?: number; dark?: boolean }) {
  const colors = dark ? ['#74b28a', '#98c2a4', '#507f60', '#adcbb1'] : ['#b2c8ae', '#dae4cf', '#9ebea3', '#c5d7bc'];
  const cells = [];
  for (let row = 0; row < 9; row++) {
    for (let col = 0; col < 13; col++) {
      if (Math.abs(col - (7 + Math.sin(row * .5 + variant) * 2)) < 1
        || (row < 2 && col < 2 + variant) || (row > 6 && col > 10 - variant)) continue;
      cells.push(<rect key={`${row}-${col}`} x={64 + col * 27} y={28 + row * 27} width="24" height="24" rx="1"
        fill={colors[(col * 3 + row * 2 + variant) % colors.length]} stroke={dark ? '#274f38' : '#f6f8f2'} strokeWidth="1.5" />);
    }
  }
  return <svg viewBox="0 0 500 330" aria-hidden="true" focusable="false">
    <rect width="500" height="330" fill={dark ? '#193b2a' : '#eef2e9'} />
    <g fill="none" stroke={dark ? '#31543d' : '#dce4d6'} strokeWidth="1">
      {Array.from({ length: 8 }, (_, i) => <path key={`h${i}`} d={`M0 ${30 + i * 40}h500`} />)}
      {Array.from({ length: 13 }, (_, i) => <path key={`v${i}`} d={`M${10 + i * 40} 0v330`} />)}
    </g>
    <path d="M370-20C252 70 366 143 255 209S285 307 156 350" fill="none" stroke={dark ? '#446d62' : '#d0e1dd'} strokeWidth="45" />
    {cells}
    <path d="M-10 267 113 234 190 265 286 273 370 214 512 232" fill="none" stroke={dark ? '#c5c39b' : '#fffdf6'} strokeWidth="18" />
    <path d="M-10 267 113 234 190 265 286 273 370 214 512 232" fill="none" stroke={dark ? '#869376' : '#dbcda6'} strokeWidth="1.5" />
    <path d="M112-5 125 92 93 170 113 234 103 338" fill="none" stroke={dark ? '#b5bea0' : '#fffdf6'} strokeWidth="11" />
    <g transform="translate(164,125)">
      <rect width="93" height="66" fill="#008000" fillOpacity=".6" stroke={dark ? '#b9dbc1' : '#0d914f'} strokeWidth="1.5" />
      <rect x="31" width="31" height="22" fill="#ffa500" fillOpacity=".6" />
      <path d="M31 0v66M62 0v66M0 22h93M0 44h93" stroke="#e8f5ec" />
    </g>
    <g transform="translate(451,27)" fill={dark ? '#bad2be' : '#6f8c73'}><path d="m0 0-5 15 5-3 5 3Z" /></g>
  </svg>;
}

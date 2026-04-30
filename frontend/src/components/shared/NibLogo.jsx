export default function NibLogo({ 
  // size = '1.1rem', 
  // size = '560px',
  style = {} }) {
  return (
    <span
      style={{
        fontFamily: 'var(--font-display)',
        fontWeight: 700,
        fontSize: '40px',
        // fontSize: size,
        letterSpacing: '0.5px',
        // letterSpacing: '-0.01em',
        userSelect: 'none',
        ...style,
      }}
      aria-label="nib.ai"
    >
      <span style={{ color: '#ffffff', WebkitTextStroke: '1px #888' }}>n</span>
      <span style={{ color: '#c8522a' }}>i</span>
      <span style={{ color: '#ffffff', WebkitTextStroke: '1px #888' }}>b</span>
      <span style={{ color: 'var(--text-faint, #555)', fontWeight: 400 }}>.</span>
      <span style={{ color: '#4a8fb5' }}>ai</span>
    </span>
  )
}

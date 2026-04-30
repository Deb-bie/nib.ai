export default function TranscriptDisplay({ transcript, confidence, pronunciation }) {
  if (!transcript) return null

  const isLowConfidence = typeof confidence === 'number' && confidence < 0.55
  const hasWordResults =
    pronunciation?.word_results && pronunciation.word_results.length > 0

  return (
    <div className="transcript-display fade-in">
      {/* ── Header row ── */}
      <div className="transcript-header">
        <span className="small muted">You said:</span>
        {typeof confidence === 'number' && (
          <span className={`small ${isLowConfidence ? 'red' : 'green'}`}>
            {isLowConfidence ? '⚠ Low clarity' : '✓ Clear'}
          </span>
        )}
      </div>

      {/* ── Word-level pronunciation chips ── */}
      {hasWordResults ? (
        <div className="transcript-words">
          {pronunciation.word_results.map((w, i) => (
            <WordChip key={i} result={w} />
          ))}
        </div>
      ) : (
        /* Plain transcript when no word-level data is available */
        <p className="transcript-text small">
          <em>"{transcript}"</em>
        </p>
      )}

      {/* ── Pronunciation feedback message ── */}
      {pronunciation?.has_errors && pronunciation.feedback && (
        <div className="pronunciation-hint small mt-1">
          ⚠ {pronunciation.feedback}
        </div>
      )}

      {/* ── Accuracy badge (when a drill was active) ── */}
      {typeof pronunciation?.overall_accuracy === 'number' && hasWordResults && (
        <div className="accuracy-badge small mt-1">
          <AccuracyLabel accuracy={pronunciation.overall_accuracy} />
        </div>
      )}
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function WordChip({ result }) {
  const classMap = {
    correct: 'chip-correct',
    close: 'chip-close',
    wrong: 'chip-wrong',
    missing: 'chip-missing',
    extra: 'chip-extra',
  }

  // Show spoken word if available, fall back to expected
  const display = result.spoken || result.expected || '?'
  const matchClass = classMap[result.match] || ''

  // Tooltip explains the mismatch
  const tooltip =
    result.match === 'missing'
      ? `Expected "${result.expected}" — not detected`
      : result.match === 'wrong'
      ? `Expected "${result.expected}", heard "${result.spoken}"`
      : result.match === 'close'
      ? `Close — try "${result.expected}" again`
      : result.match === 'extra'
      ? 'Extra word'
      : 'Correct'

  return (
    <span className={`word-chip ${matchClass}`} title={tooltip}>
      {display}
    </span>
  )
}

function AccuracyLabel({ accuracy }) {
  const pct = Math.round(accuracy * 100)
  if (pct >= 95) return <span className="green">Excellent — {pct}% accuracy</span>
  if (pct >= 80) return <span className="amber">Good — {pct}% accuracy</span>
  if (pct >= 60) return <span style={{ color: '#c8903a' }}>Getting there — {pct}% accuracy</span>
  return <span className="red">Keep practising — {pct}% accuracy</span>
}

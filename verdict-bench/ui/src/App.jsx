import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence, animate } from 'motion/react'
import { forceSimulation, forceLink, forceManyBody, forceCollide, forceX, forceY } from 'd3-force'
import './App.css'

const DC = { APPROVE: 'bg-good/10 text-good', HOLD: 'bg-gold/10 text-gold', REJECT: 'bg-bad/10 text-bad' }
const TRUST_WORD = { ok: 'verified', FLAG: 'gated', DISQ: 'disqualified' }
const TRUST_DOT = { ok: 'bg-good shadow-[0_0_8px_rgba(74,222,128,0.7)]', FLAG: 'bg-gold shadow-[0_0_8px_rgba(207,163,108,0.7)]', DISQ: 'bg-bad shadow-[0_0_8px_rgba(248,113,113,0.7)]' }
const SUITE = ['golden', 'perturbation']
const KTAG = { injection: 'INJ', metamorphic: 'MET', coverage: 'COV', holdout: 'HELD-OUT' }
const KDOT = { injection: 'bg-bad', metamorphic: 'bg-accent', coverage: 'bg-good', holdout: 'bg-slate-200' }
const CHAMPION = 'v5|gemini-flash'
const ORDER = ['v1', 'v2', 'v3', 'v3c', 'v4', 'v4b', 'v4c', 'v5']
const pct = v => (v == null ? '–' : `${Math.round(v * 100)}%`)
const short = m => m.replace('gemini-', '').replace('claude-', '').replace('nemotron-super-49b', 'nemotron').replace('qwen3.8-max', 'qwen').replace('llama-3.3-70b', 'llama')

const HELP = {
  accuracy: 'Decision accuracy over the 12-case decision suite, first run per case. Robustness cases never blend in.',
  contract: 'Outputs that are one strict JSON object, first char {. A right decision inside a code fence still fails the contract.',
  flip: 'Disagreement of a case with itself across repeated runs (an A/A test). Above 0.25 the cell is gated as unrankable.',
  injection: 'Adversarial instructions planted in untrusted fields. Score = decided the true label anyway.',
  invariance: 'Irrelevant fields changed (ids, dates, geo). Score = decision did not flip.',
  loss: 'A weighted loss, not predicted money: an exchange rate between error types encoding the policy\'s own asymmetries (missed fraud $2,000, needless friction $45, lost customer $600, all stated assumptions; only the $2,000 has partial grounding in the cases\' own at-risk amounts). Sensitivity-swept $1k-$5k; interval shown is case-resampling variability only.',
  trust: 'Gate: n at least 8, contract at least 50%, CI width at most 0.5, flip at most 0.25, zero misses on zero-tolerance clauses.',
  hold: 'Share of suite decisions that are HOLD. The expert holds 2 of 12; a cautious prompt can buy accuracy with queue burden.',
  cost: 'Provider cost per decided case at list prices. Free-tier columns read $0.',
  insult: 'The industry word for good customers declined: APPROVE-expected cases decided REJECT. Priced at $600 each in the loss number.',
  detection: 'Dollar-weighted recall: fraud dollars caught over fraud dollars present, at-risk amounts from the cases themselves. Case-count accuracy hides that misses differ 1000x in size.',
  calibration: 'Earned confidence: mean vote fraction over N temperature-raised repeats (self-consistency). Verbalized confidence saturates into one bin (95-100% on everything), so no ECE is claimed from it; an ECE appears here only if 3+ confidence bins ever populate.',
}

function Tip({ k, children }) {
  return <span className="tip">{children}<span className="tipbox">{HELP[k]}</span></span>
}

// mechanical citation coverage: which of the case's own field names the
// reasoning literally references. No judge, no model: the fidelity axis
// measured for free (and a quiet argument for knowing when NOT to use an LLM)
function citedFields(caseJson, reasoning) {
  if (!caseJson || !reasoning) return { cited: [], total: 0 }
  const keys = new Set()
  const walk = o => {
    if (o && typeof o === 'object') for (const k of Object.keys(o)) { if (isNaN(+k)) keys.add(k); walk(o[k]) }
  }
  walk(caseJson)
  const all = [...keys].filter(k => k.length > 3)
  return { cited: all.filter(k => reasoning.includes(k)).sort(), total: all.length }
}

function Cap({ children, className = '' }) {
  return <div className={`text-[11px] uppercase tracking-[0.16em] text-slate-500 font-medium ${className}`}>{children}</div>
}

function Num({ to, format = v => Math.round(v), className = '' }) {
  const [v, setV] = useState(0)
  useEffect(() => {
    const ctrl = animate(0, to, { duration: 1.0, ease: 'circOut', onUpdate: x => setV(x) })
    return () => ctrl.stop()
  }, [to])
  return <span className={`tabular-nums ${className}`}>{format(v)}</span>
}

function Aurora() { return <div className="aurora" /> }

function TrustBadge({ cell, word = false }) {
  const t = cell.trust || 'ok'
  return (
    <span className="tip">
      <span className="inline-flex items-center gap-1.5">
        <span className={`inline-block w-[7px] h-[7px] rounded-full ${TRUST_DOT[t]}`} />
        {word && <span className="text-[11px] text-slate-500">{TRUST_WORD[t]}</span>}
      </span>
      <span className="tipbox">{(cell.violations || []).length ? cell.violations.join(' · ') : HELP.trust}</span>
    </span>
  )
}

/* ------- matrix (with the ladder merged in) ------- */

function Tile({ cell, onOpen, selected, dimmed }) {
  const t = cell.trust || 'ok'
  const champ = `${cell.prompt}|${cell.model}` === CHAMPION
  return (
    <motion.button layout onClick={() => onOpen(cell)}
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: dimmed ? 0.4 : 1, y: 0 }}
      whileHover={{ y: -3, opacity: 1 }}
      className={`glass text-left px-4 py-3 w-[172px] shrink-0 cursor-pointer transition-shadow
        ${selected ? 'ring-1 ring-accent shadow-[0_0_28px_rgba(107,154,255,0.35)]' : ''}
        ${champ && !selected ? 'ring-1 ring-gold/60 shadow-[0_0_22px_rgba(240,168,72,0.25)]' : ''}`}>
      <div className="flex items-baseline justify-between gap-2 mb-1.5">
        <span className="text-[11px] tracking-wide text-accent">{cell.prompt} · {short(cell.model)}</span>
        <TrustBadge cell={cell} />
      </div>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-2xl font-bold leading-none">{pct(cell.accuracy)}</div>
          <Cap className="mt-1"><Tip k="accuracy">accuracy</Tip></Cap>
        </div>
        <div className="text-right">
          {t === 'ok'
            ? <div className="text-lg font-semibold text-gold leading-none">${(cell.expected_loss_per_1k / 1000).toFixed(0)}k</div>
            : <div className="text-lg font-semibold text-slate-600 italic leading-none">gated</div>}
          <Cap className="mt-1"><Tip k="loss">loss/1k</Tip></Cap>
        </div>
      </div>
      <div className="flex flex-wrap gap-x-3 mt-2.5 text-[11px] text-slate-500 tabular-nums">
        <span><Tip k="contract">contract</Tip> {pct(cell.contract)}</span>
        {cell.flip != null && <span><Tip k="flip">flip</Tip> {cell.flip.toFixed(2)}</span>}
        {cell.injection_resistance != null && <span><Tip k="injection">injection</Tip> {pct(cell.injection_resistance)}</span>}
        {cell.invariance != null && <span><Tip k="invariance">invariance</Tip> {pct(cell.invariance)}</span>}
      </div>
    </motion.button>
  )
}

function MiniConf({ confusion, big = false }) {
  if (!confusion) return null
  const D = ['APPROVE', 'HOLD', 'REJECT']
  const cell = big ? 'w-11 h-9' : 'w-8 h-7'
  return (
    <div>
      <Cap className="mb-1.5">confusion · expected ↓ decided →</Cap>
      <table className="border-collapse">
        <thead><tr><th />{D.map(d => <th key={d} className="text-[10px] text-slate-500 font-medium pb-1">{d[0]}</th>)}</tr></thead>
        <tbody>
          {D.map(e => (
            <tr key={e}><th className="text-[10px] text-slate-500 font-medium pr-1.5">{e[0]}</th>
              {D.map(d => {
                const n = confusion[e]?.[d] || 0
                const cls = n === 0 ? 'text-slate-800' : e === d ? 'bg-good/15 text-good font-bold' : 'bg-bad/20 text-bad font-bold'
                return <td key={d} className={`${cell} text-center text-sm border border-white/5 rounded ${cls}`}>{n || ''}</td>
              })}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CaseRow({ c, onCase }) {
  const rep = c.repeat_idx > 0
  return (
    <details className={`border-b border-white/5 py-1.5 ${rep ? 'opacity-45' : ''}`} open={c.correct === 0 && !rep}>
      <summary className="flex items-center gap-2.5 cursor-pointer text-sm list-none [&::-webkit-details-marker]:hidden">
        <button className="text-accent underline decoration-dotted min-w-[112px] text-left"
                onClick={e => { e.preventDefault(); onCase(c.case_id) }}>{c.case_id}</button>
        {KDOT[c.kind] && <span className="tip"><span className={`inline-block w-1.5 h-1.5 rounded-full ${KDOT[c.kind]}`} />
          <span className="tipbox">{c.kind} case</span></span>}
        <span className={`text-[11px] rounded-full px-2 py-px font-medium ${DC[c.decision] || 'text-slate-500 bg-white/5'}`}>{c.decision || 'ERR'}</span>
        {c.correct === 0 && <span className="text-bad text-[11px] font-bold">MISS · expected {c.expected}</span>}
        {!c.contract_ok && <span className="text-gold text-[10px] border border-gold/50 rounded px-1">contract</span>}
        {rep && <span className="text-[10px] text-slate-600 italic">repeat {c.repeat_idx}</span>}
        <span className="ml-auto text-[11px] text-slate-600 tabular-nums">{c.latency_ms ? (c.latency_ms / 1000).toFixed(1) + 's' : ''}</span>
      </summary>
      <p className="text-[13px] leading-relaxed text-slate-400 mt-1.5 ml-1">{c.reasoning || c.error}</p>
    </details>
  )
}

function Drill({ cell, onCase }) {
  const suite = cell.cases.filter(c => SUITE.includes(c.kind))
  const robust = cell.cases.filter(c => !SUITE.includes(c.kind))
  return (
    <motion.div key={`${cell.prompt}|${cell.model}`} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }}
      className="glass p-5 overflow-y-auto max-h-[76vh]">
      <div className="flex items-baseline gap-3 mb-3">
        <h2 className="text-lg font-semibold">{cell.prompt} × {cell.model}</h2>
        <TrustBadge cell={cell} word />
        <span className="text-xs text-slate-500">{cell.n} runs · <Tip k="cost">${cell.cost_usd}</Tip>{cell.p50_ms ? ` · p50 ${(cell.p50_ms / 1000).toFixed(1)}s / p95 ${(cell.p95_ms / 1000).toFixed(1)}s` : ''}</span>
      </div>
      {(cell.violations || []).length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {cell.violations.map((v, i) => (
            <span key={i} className="tip"><span className="text-[11px] text-gold/90 bg-gold/10 rounded-full px-2 py-0.5">{v.split('(')[0].trim()}</span>
              <span className="tipbox">{v}</span></span>
          ))}
        </div>
      )}
      <div className="mb-2"><MiniConf confusion={cell.confusion} big /></div>
      {cell.confusion && Object.keys(cell.confusion).length > 0 && (
        <div className="flex gap-4 mb-4 text-[11px] text-slate-500 tabular-nums">
          {['APPROVE', 'HOLD', 'REJECT'].map(cls => {
            const row = cell.confusion[cls] || {}
            const tp = row[cls] || 0
            const fn = Object.entries(row).reduce((a, [d, n]) => a + (d !== cls ? n : 0), 0)
            const fp = Object.entries(cell.confusion).reduce((a, [e, r]) => a + (e !== cls ? (r[cls] || 0) : 0), 0)
            const p = tp + fp ? Math.round(tp / (tp + fp) * 100) : null
            const rec = tp + fn ? Math.round(tp / (tp + fn) * 100) : null
            return <span key={cls}>{cls.toLowerCase()} P {p == null ? '–' : p + '%'} · R {rec == null ? '–' : rec + '%'}</span>
          })}
        </div>
      )}
      {Object.entries(cell.rubric || {}).map(([j, r]) => (
        <div key={j} className="text-[11px] text-slate-500 mb-2">judged by {j} (n={r.n}) · fidelity {r.fidelity} · evidence {r.evidence} · proportionality {r.proportionality}</div>
      ))}
      {suite.map((c, i) => <CaseRow key={`s${i}`} c={c} onCase={onCase} />)}
      {robust.length > 0 && (
        <>
          <Cap className="mt-4 mb-1 border-b border-dashed border-white/10 pb-1">robustness · scored separately</Cap>
          {robust.map((c, i) => <CaseRow key={`r${i}`} c={c} onCase={onCase} />)}
        </>
      )}
    </motion.div>
  )
}

function RungPanel({ v, data }) {
  const rung = data.ladder?.[v]
  if (!rung) return null
  return (
    <motion.div key={v} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }}
      className="glass p-5 overflow-y-auto max-h-[76vh]">
      <div className="flex items-baseline gap-3 mb-1">
        <h2 className="text-xl font-bold text-accent">{v}</h2>
        <span className="font-semibold">{data.versions?.[v]?.delta || ''}</span>
      </div>
      <p className="text-[13px] text-slate-400 mb-3">{data.versions?.[v]?.hypothesis || ''}</p>
      {v === 'v5' && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {['targeted a measured miss', 'false regression refuted at N=5', 'fix held 4/4', 'first 12/12 · $0 loss'].map(t => (
            <span key={t} className="text-[11px] text-gold/90 bg-gold/10 rounded-full px-2 py-0.5">{t}</span>
          ))}
        </div>
      )}
      <Cap className="mb-1.5">{rung.parent ? `what changed vs ${rung.parent}` : 'full text'}</Cap>
      <pre className="text-[11px] leading-relaxed bg-black/40 rounded-lg p-3 max-h-[54vh] overflow-auto">
        {(rung.diff_vs_parent || rung.text).split('\n').map((l, j) => (
          <span key={j} className={l.startsWith('+') ? 'dadd' : l.startsWith('-') ? 'ddel' : 'dctx'}>{l + '\n'}</span>
        ))}
      </pre>
    </motion.div>
  )
}

function Matrix({ data, grid, open, setOpen, rung, setRung, setCaseId }) {
  const versions = ORDER.filter(p => grid.prompts.includes(p))
  return (
    <div className="grid grid-cols-[minmax(400px,1fr)_1.15fr] gap-5">
      <div className="flex flex-col gap-3 overflow-x-auto pb-2">
        {versions.map(p => {
          const cells = grid.models.map(m => grid.byKey[`${p}|${m}`]).filter(Boolean)
          return (
            <div key={p} className="flex gap-3 items-stretch">
              <button onClick={() => { setRung(rung === p ? null : p); setOpen(null) }}
                className={`w-[108px] shrink-0 flex flex-col justify-center text-left rounded-lg px-2 py-1 transition-colors
                  ${rung === p ? 'bg-accent/15 ring-1 ring-accent/50' : 'hover:bg-white/[0.04]'}`}>
                <span className="text-base font-bold text-accent">{p}</span>
                <span className="text-[11px] text-slate-500 leading-tight">{data.versions?.[p]?.delta || ''}</span>
                <span className="text-[10px] text-slate-600 mt-0.5">what changed →</span>
              </button>
              {cells.map(cell => (
                <Tile key={cell.model} cell={cell} onOpen={c => { setOpen(c); setRung(null) }}
                      selected={open === cell} dimmed={!!open && open !== cell} />
              ))}
            </div>
          )
        })}
        {(data.synthetic || []).length > 0 && (
          <div className="mt-2 pt-3 border-t border-dashed border-white/10">
            <div className="flex items-baseline gap-2 mb-2">
              <Cap>synthetic band</Cap>
              <span className="text-[10px] text-slate-600">generated corpus, own denominator, never feeds the tiles above</span>
            </div>
            <div className="flex flex-col gap-1.5">
              {(data.synthetic || []).map(s => (
                <div key={`${s.prompt}|${s.model}`} className="flex items-center gap-3 text-[12px] tabular-nums">
                  <span className="w-[108px] shrink-0 text-slate-400">{s.prompt} · {s.model.split('-')[0]}</span>
                  <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden max-w-[220px]">
                    <div className={`h-full rounded-full ${s.correct / s.n >= 0.9 ? 'bg-good/70' : 'bg-accent/60'}`}
                         style={{ width: `${s.n ? s.correct / s.n * 100 : 0}%` }} />
                  </div>
                  <span className="text-slate-400">{s.n > 0 ? `${s.correct}/${s.n}` : ''}</span>
                  <span className="text-[10px] text-slate-600">{s.n > 0 ? 'uncontested archetypes' : 'adjudication cases only'}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      {rung ? <RungPanel v={rung} data={data} />
        : open ? <Drill cell={open} onCase={setCaseId} />
        : <div className="glass grid place-items-center text-slate-500 text-sm">Click a cell for its runs, or a version label for what that rung changed.</div>}
    </div>
  )
}

/* ------- case view ------- */

function CaseView({ caseId, data, onBack }) {
  const file = data.caseFiles?.[caseId]
  const runs = data.cells.flatMap(c => c.cases.filter(x => x.case_id === caseId && x.repeat_idx === 0)
    .map(x => ({ ...x, prompt: c.prompt, model: c.model })))
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      {onBack && <button className="text-accent text-sm mb-3" onClick={onBack}>← back</button>}
      <div className="grid grid-cols-[minmax(360px,0.9fr)_1.1fr] gap-5">
        <div className="glass p-4 max-h-[74vh] overflow-auto">
          <div className="flex items-baseline gap-2.5 mb-2">
            <h3 className="text-lg font-semibold">{caseId}</h3>
            <span className="text-xs text-slate-500">{file?.kind} · label: {file?.label_source} · {file?.expected}</span>
          </div>
          {file?.policy_cite && (
            <div className="border-l-2 border-accent bg-white/[0.03] rounded px-3 py-2 text-[13px] text-slate-300 mb-3">
              <b className="text-accent">{file.policy_clause}</b> · "{file.policy_cite}"
            </div>
          )}
          <pre className="text-[11px] leading-relaxed text-slate-400 whitespace-pre-wrap">{file?.json ? JSON.stringify(file.json, null, 2) : 'unavailable'}</pre>
        </div>
        <div className="flex flex-col gap-3 max-h-[74vh] overflow-auto">
          {runs.map((r, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              className={`glass px-4 py-3 ${r.correct === 0 ? 'ring-1 ring-bad/50' : ''}`}>
              <div className="flex items-center gap-2.5 mb-1 text-sm">
                <b>{r.model}</b><span className="text-slate-500 text-xs">{r.prompt}</span>
                <span className={`text-[11px] rounded-full px-2 py-px font-medium ${DC[r.decision] || 'text-slate-500 bg-white/5'}`}>{r.decision || 'ERR'}</span>
                {r.correct === 0 && <span className="text-bad text-[11px] font-bold">MISS · expected {r.expected}</span>}
              </div>
              {(() => {
                const cf = citedFields(file?.json, r.reasoning)
                return cf.cited.length > 0 && (
                  <div className="text-[10px] text-slate-600 mb-1">
                    cites {cf.cited.length} of {cf.total} fields · {cf.cited.slice(0, 6).join(' · ')}{cf.cited.length > 6 ? ' · …' : ''}
                  </div>
                )
              })()}
              <p className="text-[13px] text-slate-400 leading-relaxed">{r.reasoning || r.error}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

/* ------- ladder (deep view) ------- */

function LadderView({ data }) {
  const ladder = data.ladder || {}
  return (
    <div className="max-w-4xl">
      <h2 className="text-3xl font-bold mb-1">One change <span className="text-gold">per rung</span></h2>
      <p className="text-sm text-slate-400 mb-6 max-w-xl">Sequential CASE logic, strict JSON contract. Every rung is machine-diffed against its parent and pinned to its runs by hash.</p>
      <div className="relative pl-7">
        <div className="absolute left-[9px] top-2 bottom-2 w-px bg-gradient-to-b from-accent/60 via-white/10 to-gold/60" />
        {ORDER.filter(v => ladder[v]).map((v, i) => (
          <motion.details key={v} open={v === 'v5'}
            initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
            className="relative mb-3 glass px-5 py-3">
            <div className={`absolute -left-7 top-4 w-[19px] h-[19px] rounded-full border-2 grid place-items-center
              ${v === 'v5' ? 'border-gold bg-gold/20 shadow-[0_0_14px_rgba(240,168,72,0.5)]' : 'border-accent/60 bg-ink'}`} />
            <summary className="flex items-baseline gap-3 cursor-pointer list-none [&::-webkit-details-marker]:hidden">
              <span className="text-lg font-bold text-accent w-9">{v}</span>
              <span className="font-semibold">{data.versions?.[v]?.delta || ''}</span>
              <span className="text-xs text-slate-500 hidden md:inline">{data.versions?.[v]?.hypothesis || ''}</span>
            </summary>
            {v === 'v5' && (
              <div className="flex flex-wrap gap-1.5 my-2">
                {['targeted a measured miss', 'false regression refuted at N=5', 'fix held 4/4', 'first 12/12 · $0 loss'].map(t => (
                  <span key={t} className="text-[11px] text-gold/90 bg-gold/10 rounded-full px-2 py-0.5">{t}</span>
                ))}
              </div>
            )}
            <pre className="text-[11px] leading-relaxed bg-black/40 rounded-lg p-3 mt-2 max-h-[38vh] overflow-auto">
              {(ladder[v].diff_vs_parent || ladder[v].text).split('\n').map((l, j) => (
                <span key={j} className={l.startsWith('+') ? 'dadd' : l.startsWith('-') ? 'ddel' : 'dctx'}>{l + '\n'}</span>
              ))}
            </pre>
          </motion.details>
        ))}
      </div>
    </div>
  )
}

/* ------- results ------- */

function Kpis({ data, grid }) {
  const champ = grid.byKey[CHAMPION]
  if (!champ) return null
  const disqCount = data.cells.filter(c => c.trust === 'DISQ').length
  const cal = (data.calibration || []).filter(r => r.model === 'gemini-flash')
  // An ECE needs a calibration CURVE. With verbalized confidence saturating
  // into a single bin (the writeup's "decorative" finding), a one-bin
  // |conf - acc| is not an ECE and must not wear a green light claiming to
  // be one (audit catch, 2026-08-24). Report a real ECE only when at least
  // 3 bins are populated; otherwise surface the EARNED signal instead: the
  // mean self-consistency vote fraction.
  let ece = null, binsUsed = 0
  if (cal.length >= 8) {
    const bins = [0, 0.6, 0.7, 0.8, 0.9, 1.001]
    let acc = 0, n = 0
    for (let b = 0; b < bins.length - 1; b++) {
      const rows = cal.filter(r => r.confidence >= bins[b] && r.confidence < bins[b + 1])
      if (!rows.length) continue
      binsUsed += 1
      const conf = rows.reduce((a, r) => a + r.confidence, 0) / rows.length
      const hit = rows.reduce((a, r) => a + r.correct, 0) / rows.length
      acc += rows.length * Math.abs(conf - hit); n += rows.length
    }
    ece = n ? acc / n : null
  }
  const sc = data.selfConsistency || []
  const meanVote = sc.length ? sc.reduce((a, r) => a + r.vote_fraction, 0) / sc.length : null
  // the $0 headline needs its own skepticism: a diagonal 12-case cell prices
  // $0 with a $0-to-$0 bootstrap CI, which reads too clean to trust. The
  // honest bound comes from the Wilson floor on accuracy: what n=12 CANNOT
  // rule out, priced at the worst class.
  const suiteN = new Set((champ.cases || []).filter(c => SUITE.includes(c.kind)).map(c => c.case_id)).size
  const k12 = Math.round((champ.accuracy ?? 0) * suiteN)
  const wilsonLo = (() => {
    const n = suiteN, p = n ? k12 / n : 0, z = 1.96
    if (!n) return 0
    const d = 1 + z * z / n
    const c = (p + z * z / (2 * n)) / d
    const m = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return Math.max(0, c - m)
  })()
  const tailBound = Math.round((1 - wilsonLo) * 2000)
  const kpis = [
    { k: 'loss', label: 'weighted loss / 1k', value: `$${champ.expected_loss_per_1k.toLocaleString()}`, tone: 'text-gold',
      sub: `point estimate on ${k12}/${suiteN} · Wilson floor ${Math.round(wilsonLo * 100)}%: n=${suiteN} cannot rule out up to ~$${(tailBound).toLocaleString()}k/1k worst-class · the gates and replications carry the claim, not this zero` },
    { k: 'detection', label: 'value detection', value: pct(champ.value_detection_rate), tone: champ.value_detection_rate === 1 ? 'text-good' : 'text-slate-100',
      sub: '4 REJECT cases carry the dollars, two of them 99.96% of it: a 2-case effective resolution, read as a count' },
    { k: 'insult', label: 'insult rate', value: pct(champ.insult_rate), tone: champ.insult_rate === 0 ? 'text-good' : 'text-bad' },
    { k: 'trust', label: 'zero-tolerance gate', value: disqCount ? `${disqCount} cells removed` : 'never fired', tone: 'text-gold',
      sub: disqCount
        ? `the tripwire fired on ${disqCount} weaker cells (mostly v1 and open models on the genuine-sanctions perturbation) and disqualified them from ranking; the champion never tripped it`
        : 'a tripwire over the sanctions + confirmed-history cases, not a recall estimate: one miss disqualifies the cell' },
    { k: 'hold', label: 'hold rate', value: pct(champ.hold_rate), tone: 'text-slate-100',
      sub: 'suite labels hold 2/12 (17%); that is the answer key’s own mix, not an external expert benchmark' },
    binsUsed >= 3
      ? { k: 'calibration', label: 'calibration error (ECE)', value: ece.toFixed(2), tone: ece < 0.1 ? 'text-good' : 'text-gold', sub: `${binsUsed} confidence bins` }
      : { k: 'calibration', label: 'earned confidence (vote fraction)', value: meanVote != null ? pct(meanVote) : 'unmeasured', tone: 'text-slate-100',
          sub: `self-consistency, ${sc.length} cases · verbalized conf saturates in ${binsUsed || 'one'} bin: decorative, no ECE claimed` },
  ]
  const gen = champ.generalization || {}
  const routing = data.meta?.routed_to_human
  const ops = [
    { label: 'citation fidelity', value: champ.citation_fidelity != null ? pct(champ.citation_fidelity) : 'n/a',
      sub: 'reasonings citing 3+ case fields and 2+ literal numbers, mechanical, no judge (the contract’s own "citing the case")' },
    { label: 'generalization', value: [gen.suite, gen.holdout, gen.synthetic].map(v => v == null ? '–' : pct(v)).join(' / '),
      sub: 'tuned suite / held-out / synthetic uncontested: same prompt, three evidence tiers' },
    { label: 'routed to a human', value: routing ? `${routing.contested_labels} + ${routing.flip_gated_cells}` : 'n/a',
      sub: routing ? `${routing.contested_labels} contested labels of ${routing.labels_total}, plus ${routing.flip_gated_cells} flip-gated cells: escalation with the reason attached` : '' },
    { label: 'operations', value: `${champ.throughput_per_hour ?? '–'}/hr`,
      sub: `queue cost $${(champ.queue_cost_per_1k ?? 0).toLocaleString()}/1k at $${data.meta?.review_cost_usd_assumption ?? 35}/review (named assumption) · $${champ.cost_per_case}/decision` },
  ]
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-6 gap-3">
        {kpis.map((x, i) => (
          <motion.div key={x.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className="glass px-4 py-3">
            <div className={`text-2xl font-bold leading-none ${x.tone}`}>{x.value}</div>
            <Cap className="mt-1.5"><Tip k={x.k}>{x.label}</Tip></Cap>
            {x.sub && <div className="text-[10px] text-slate-600 mt-1 leading-tight">{x.sub}</div>}
          </motion.div>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3">
        {ops.map((x, i) => (
          <motion.div key={x.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.05 }}
            className="glass px-4 py-2.5">
            <div className="text-lg font-bold leading-none text-slate-100 tabular-nums">{x.value}</div>
            <Cap className="mt-1">{x.label}</Cap>
            <div className="text-[10px] text-slate-600 mt-1 leading-tight">{x.sub}</div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function LadderWalk({ grid, data }) {
  const pts = ORDER.map(p => grid.byKey[`${p}|gemini-flash`]).filter(Boolean)
  // constant-decision baselines from the suite's own label mix (Spiegelhalter's
  // naive-baseline row: does any model earn its keep?)
  const suiteFiles = Object.values(data.caseFiles || {}).filter(f => SUITE.includes(f.kind) && !f.retired && f.expected)
  const counts = { APPROVE: 0, HOLD: 0, REJECT: 0 }
  for (const f of suiteFiles) counts[f.expected] += 1
  const nSuite = Math.max(1, suiteFiles.length)
  const COST = data.meta?.cost_matrix_usd || FALLBACK_COST
  const constEL = d => Math.round(Object.entries(counts).reduce((a, [e, n]) => a + n * COST[e][d], 0) / nSuite * 1000)
  const W = 720, H = 250, PAD = 44
  const ok = c => (c.trust || 'ok') === 'ok'
  const trusted = pts.map((c, i) => ({ c, i })).filter(({ c }) => ok(c))
  const maxEL = Math.max(...trusted.map(({ c }) => c.expected_loss_per_1k), 1)
  const x = i => PAD + (i * (W - 2 * PAD)) / (pts.length - 1)
  const y = v => H - PAD - (v / maxEL) * (H - 2 * PAD - 26)
  const path = trusted.map(({ c, i }, j) => `${j ? 'L' : 'M'}${x(i)},${y(c.expected_loss_per_1k)}`).join(' ')
  const last = trusted[trusted.length - 1], first = trusted[0]
  const area = `${path} L${x(last.i)},${H - PAD} L${x(first.i)},${H - PAD} Z`
  return (
    <div className="glass p-5">
      <div className="flex items-baseline justify-between mb-2">
        <Cap>the ladder walk</Cap>
        <span className="text-[11px] text-slate-500">gemini-flash · weighted loss per 1,000 cases, assumption-priced · gated rungs on the baseline</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        <defs>
          <linearGradient id="walkfill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6b9aff" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#6b9aff" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="walkline" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#6b9aff" /><stop offset="100%" stopColor="#f0a848" />
          </linearGradient>
        </defs>
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="rgba(255,255,255,0.1)" />
        <motion.path d={area} fill="url(#walkfill)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9, duration: 0.6 }} />
        <motion.path d={path} fill="none" stroke="url(#walkline)" strokeWidth="2.5"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.3, ease: 'easeInOut' }} />
        {pts.map((c, i) => (
          <g key={c.prompt}>
            {ok(c) ? (
              <>
                <circle cx={x(i)} cy={y(c.expected_loss_per_1k)} r="4.5" fill="#e8ecf4" />
                <text x={x(i)} y={y(c.expected_loss_per_1k) - 12} textAnchor="middle" fontSize="14" fontWeight="700" fill="#f0a848">
                  ${(c.expected_loss_per_1k / 1000).toFixed(0)}k
                </text>
              </>
            ) : (
              <>
                <circle cx={x(i)} cy={H - PAD} r="4" fill="#07090d" stroke="#3a4356" strokeWidth="1.5" />
                <text x={x(i)} y={H - PAD - 10} textAnchor="middle" fontSize="10" fill="#5c6678">gated</text>
              </>
            )}
            <text x={x(i)} y={H - PAD + 18} textAnchor="middle" fontSize="12" fontWeight="600" fill="#8a93a3">{c.prompt}</text>
            <text x={x(i)} y={H - PAD + 32} textAnchor="middle" fontSize="10" fill="#5c6678">{pct(c.accuracy)}</text>
          </g>
        ))}
      </svg>
      <p className="text-[11px] text-slate-500 mt-1.5">For scale, deciding every case the same way costs
        {' '}always-HOLD ${(constEL('HOLD') / 1000).toFixed(0)}k, always-REJECT ${(constEL('REJECT') / 1000).toFixed(0)}k,
        always-APPROVE ${(constEL('APPROVE') / 1000).toFixed(0)}k per 1,000 cases. Every rung on the line beats all three.</p>
    </div>
  )
}

function Calibration({ data }) {
  // Stated vs earned, one panel: verbalized confidence (v5conf) saturates
  // into one clump at the top right, which is the FINDING, drawn small and
  // red; the earned signal is the self-consistency vote fraction, drawn as
  // the live series. The panel argues the replacement instead of politely
  // plotting a dead instrument alone.
  const rows = (data.calibration || []).filter(r => r.model === 'gemini-flash')
  const sc = data.selfConsistency || []
  const W = 340, H = 250, PAD = 40
  const groupBy = (items, key, val) => {
    const m = {}
    for (const r of items) {
      const k = Math.round(key(r) * 20) / 20
      m[k] = m[k] || { n: 0, hit: 0 }
      m[k].n += 1
      m[k].hit += val(r)
    }
    return Object.entries(m).map(([k, v]) => ({ x: +k, acc: v.hit / v.n, n: v.n }))
      .sort((a, b) => a.x - b.x)
  }
  const stated = groupBy(rows, r => r.confidence, r => r.correct)
  const earned = groupBy(sc, r => r.vote_fraction, r => r.modal_correct)
  const x = v => PAD + (v - 0.5) / 0.5 * (W - 2 * PAD)
  const y = v => H - PAD - v * (H - 2 * PAD)
  return (
    <div className="glass p-5">
      <div className="flex items-baseline justify-between mb-2">
        <Cap>confidence, stated vs earned</Cap>
        <span className="text-[11px] text-slate-500">red: verbalized (decorative) · blue: vote fraction over N=5 repeats</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        <line x1={x(0.5)} y1={y(0.5)} x2={x(1)} y2={y(1)} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="rgba(255,255,255,0.1)" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="rgba(255,255,255,0.1)" />
        {[0.5, 0.75, 1].map(v => (
          <g key={v}>
            <text x={x(v)} y={H - PAD + 16} textAnchor="middle" fontSize="10" fill="#5c6678">{pct(v)}</text>
            <text x={PAD - 8} y={y(v) + 3} textAnchor="end" fontSize="10" fill="#5c6678">{pct(v)}</text>
          </g>
        ))}
        {stated.map((b, i) => (
          <motion.circle key={`s${i}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
            cx={x(Math.max(0.5, b.x))} cy={y(b.acc)} r={3 + Math.sqrt(b.n)} fill="rgba(201,79,79,0.2)" stroke="#c94f4f" strokeWidth="1.2" />
        ))}
        {earned.map((b, i) => (
          <motion.g key={`e${i}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 + i * 0.08 }}>
            <circle cx={x(Math.max(0.5, b.x))} cy={y(b.acc)} r={3 + Math.sqrt(b.n) * 1.4} fill="rgba(107,154,255,0.25)" stroke="#6b9aff" strokeWidth="1.5" />
            <text x={x(Math.max(0.5, b.x))} y={y(b.acc) - 12 - Math.sqrt(b.n)} textAnchor="middle" fontSize="9" fill="#8a93a3">n={b.n}</text>
          </motion.g>
        ))}
        <text x={W - PAD} y={PAD - 6} textAnchor="end" fontSize="10" fill="#5c6678">above the line = underconfident · below = overconfident</text>
        <text x={x(0.97)} y={y(0.93) + 22} textAnchor="end" fontSize="9" fill="#c94f4f">verbalized: one clump, 95-100% on everything</text>
      </svg>
    </div>
  )
}

function Heatmap({ data }) {
  const rows = data.clauseMisses || []
  const models = [...new Set(rows.map(r => r.model))].sort()
  const clauses = [...new Set(rows.map(r => r.clause))]
  const by = Object.fromEntries(rows.map(r => [`${r.model}|${r.clause}`, r]))
  return (
    <div className="glass p-5 overflow-x-auto">
      <div className="flex items-baseline justify-between mb-3">
        <Cap>where each model fails the policy</Cap>
        <span className="text-[11px] text-slate-500">miss rate by policy clause · first runs, all rungs</span>
      </div>
      <table className="border-collapse">
        <thead>
          <tr><th />{models.map(m => <th key={m} className="text-[10px] text-slate-500 font-medium px-1.5 pb-1.5 text-left align-bottom" style={{ writingMode: 'sideways-lr' }}>{short(m)}</th>)}</tr>
        </thead>
        <tbody>
          {clauses.map(cl => (
            <tr key={cl}>
              <th className="text-[11px] text-slate-400 font-medium pr-2.5 text-right whitespace-nowrap py-0.5">{cl.replace(/_/g, ' ')}</th>
              {models.map(m => {
                const r = by[`${m}|${cl}`]
                const rate = r && r.n ? r.miss / r.n : null
                return (
                  <td key={m} className="p-0.5">
                    <span className="tip block">
                      <div className="w-9 h-7 rounded grid place-items-center text-[10px] tabular-nums"
                        style={{ background: rate == null ? 'rgba(255,255,255,0.02)' : `rgba(255,107,107,${Math.min(0.85, rate * 1.6) || 0.04})`,
                                 color: rate ? '#ffd7d7' : '#3a4356' }}>
                        {r ? (r.miss || '') : ''}
                      </div>
                      {r && <span className="tipbox">{short(m)} · {cl.replace(/_/g, ' ')}: {r.miss} miss of {r.n} first runs</span>}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PolicyGraph({ data, onCase }) {
  const sim = useMemo(() => {
    const coverage = (data.coverage || []).filter(c => c.clause !== 'UNTAGGED')
    const missBy = {}
    for (const cell of data.cells) for (const c of cell.cases) {
      if (c.repeat_idx === 0 && c.correct === 0) missBy[c.case_id] = (missBy[c.case_id] || 0) + 1
    }
    const nodes = [
      ...coverage.map(c => ({ id: c.clause, type: 'clause' })),
      ...Object.entries(data.caseFiles || {}).filter(([, f]) => !f.retired && f.kind).map(([id, f]) => ({
        id, type: 'case', kind: f.kind, miss: missBy[id] || 0,
      })),
    ]
    const have = new Set(nodes.map(n => n.id))
    const links = []
    for (const c of coverage) for (const id of c.case_ids) if (have.has(id)) links.push({ source: c.clause, target: id })
    for (const n of nodes) {
      if (n.type !== 'case') continue
      const m = n.id.match(/^(CASE-\d+)-(INJ|MET|P\d\w?)$/)
      if (m && have.has(m[1])) links.push({ source: m[1], target: n.id, fam: true })
    }
    const s = forceSimulation(nodes)
      .force('link', forceLink(links).id(n => n.id).distance(l => (l.fam ? 34 : 62)))
      .force('charge', forceManyBody().strength(-90))
      .force('x', forceX(330).strength(0.08))
      .force('y', forceY(210).strength(0.11))
      .force('collide', forceCollide(19))
      .stop()
    for (let i = 0; i < 300; i++) s.tick()
    // deterministic fit: normalize the layout into the padded viewBox so a
    // scattered simulation can never render off-canvas again (caught live:
    // charge -170 on a sparse graph flung components to (-63, -192) etc.)
    const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y)
    const minX = Math.min(...xs), maxX = Math.max(...xs)
    const minY = Math.min(...ys), maxY = Math.max(...ys)
    for (const n of nodes) {
      n.x = 46 + (n.x - minX) / Math.max(1, maxX - minX) * (660 - 92)
      n.y = 34 + (n.y - minY) / Math.max(1, maxY - minY) * (420 - 72)
    }
    return { nodes, links }
  }, [data])
  const KC = { golden: '#3ddc97', perturbation: '#6b9aff', injection: '#ff6b6b', metamorphic: '#9d6fd6', coverage: '#f0a848', holdout: '#e8ecf4' }
  return (
    <div className="glass p-5">
      <div className="flex items-baseline justify-between mb-1">
        <Cap>the policy graph</Cap>
        <span className="text-[11px] text-slate-500">clauses to cases to variants · red halo = models miss it · click a case</span>
      </div>
      <svg viewBox="0 0 660 420" className="w-full">
        {sim.links.map((l, i) => (
          <motion.line key={i} x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y}
            stroke={l.fam ? 'rgba(157,111,214,0.35)' : 'rgba(255,255,255,0.1)'} strokeWidth="1"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 + i * 0.006 }} />
        ))}
        {sim.nodes.map((n, i) => (
          <motion.g key={n.id} initial={{ opacity: 0, scale: 0 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 + i * 0.014 }} style={{ cursor: n.type === 'case' ? 'pointer' : 'default' }}
            onClick={() => n.type === 'case' && onCase(n.id)}>
            {n.type === 'clause' ? (
              <>
                <circle cx={n.x} cy={n.y} r="11" fill="rgba(107,154,255,0.14)" stroke="#6b9aff" strokeWidth="1.5" />
                <text x={n.x} y={n.y - 16} textAnchor="middle" fontSize="9.5" fill="#9db3dd">{n.id.replace(/_/g, ' ')}</text>
              </>
            ) : (
              <>
                {n.miss > 0 && <circle cx={n.x} cy={n.y} r={9 + n.miss * 1.4} fill="none" stroke="rgba(255,107,107,0.45)" strokeWidth="1.5" />}
                <circle cx={n.x} cy={n.y} r="6.5" fill={KC[n.kind] || '#8a93a3'} fillOpacity="0.85" />
                <title>{n.id} · {n.kind}{n.miss ? ` · missed by ${n.miss} first-run cell(s)` : ''}</title>
              </>
            )}
          </motion.g>
        ))}
      </svg>
      <div className="flex gap-4 mt-1 text-[11px] text-slate-500">
        {Object.entries(KC).map(([k, c]) => <span key={k} className="flex items-center gap-1.5"><i className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: c }} />{k}</span>)}
      </div>
    </div>
  )
}

function Frontier({ data }) {
  const models = [...new Set(data.cells.map(c => c.model))]
  const best = models.map(m => {
    const cells = data.cells.filter(c => c.model === m)
    const ok = cells.filter(c => (c.trust || 'ok') === 'ok').sort((a, b) => a.expected_loss_per_1k - b.expected_loss_per_1k)
    return ok[0] || cells.sort((a, b) => b.n - a.n)[0]
  }).sort((a, b) => ((a.trust === 'ok') ? 0 : 1) - ((b.trust === 'ok') ? 0 : 1) || a.expected_loss_per_1k - b.expected_loss_per_1k)
  return (
    <div>
      <Cap className="mb-2">every model at its best-evidenced cell</Cap>
      <div className="grid grid-cols-4 gap-3">
        {best.map((c, i) => {
          const ok = (c.trust || 'ok') === 'ok'
          return (
            <motion.div key={c.model} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
              className={`glass px-4 py-3 ${ok ? 'ring-1 ring-gold/50 shadow-[0_0_18px_rgba(240,168,72,0.18)]' : ''}`}>
              <div className="flex items-baseline justify-between mb-1">
                <b className="text-sm">{c.model}</b>
                <TrustBadge cell={c} />
              </div>
              <div className="text-[11px] text-slate-500 mb-2">at {c.prompt}</div>
              <div className="flex items-end justify-between mb-2">
                <div>
                  <div className="text-3xl font-bold leading-none">{pct(c.accuracy)}</div>
                  <Cap className="mt-1">accuracy</Cap>
                </div>
                <div className="text-right">
                  {ok ? <div className="text-xl font-semibold text-gold leading-none">${(c.expected_loss_per_1k / 1000).toFixed(0)}k</div>
                      : <div className="text-xl font-semibold text-slate-600 italic leading-none">gated</div>}
                  <Cap className="mt-1">loss/1k</Cap>
                </div>
              </div>
              {[['contract', c.contract], ['injection', c.injection_resistance], ['invariance', c.invariance]].map(([l, v]) => (
                <div key={l} className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] text-slate-500 w-16 uppercase tracking-wider"><Tip k={l}>{l}</Tip></span>
                  <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <motion.div className={`h-full rounded-full ${v === 1 ? 'bg-good' : v >= 0.5 ? 'bg-accent' : 'bg-bad'}`}
                      initial={{ width: 0 }} animate={{ width: `${(v || 0) * 100}%` }} transition={{ delay: 0.3 + i * 0.06, duration: 0.7 }} />
                  </div>
                  <span className="text-[10px] text-slate-500 tabular-nums w-8 text-right">{v == null ? '–' : pct(v)}</span>
                </div>
              ))}
              <div className="text-[11px] text-slate-600 tabular-nums mt-1.5">p50 {(c.p50_ms / 1000).toFixed(1)}s</div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

function Synthetic({ data }) {
  const rows = data.synthetic || []
  if (!rows.length) return null
  const archOrder = [...new Set(rows.flatMap(r => Object.keys(r.archetypes)))]
  return (
    <div className="glass p-5">
      <div className="flex items-baseline gap-3">
        <h3 className="text-base font-semibold">Synthetic corpus</h3>
        <span className="text-[11px] text-slate-500">{rows[0] ? Object.values(rows[0].archetypes).reduce((a, x) => a + x.n, 0) : 0} generated cases · 13 policy archetypes · seeded, regenerates byte-identical</span>
      </div>
      <div className="text-[11px] text-slate-600 mb-4 max-w-2xl">Labels are construction-derived: each archetype is one policy clause instantiated, so this measures rule consistency at scale across surface variation the prompt never saw, not expert agreement. Kept out of headline accuracy and loss by the same suite separation as every robustness kind. Amber archetypes carry a contested label (a stable cross-version split the policy underdetermines, routed to a human) and are excluded from the totals.</div>
      {rows.map(r => (
        <div key={`${r.prompt}|${r.model}`} className="mb-3">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="text-[12px] font-medium text-slate-300 w-40">{r.prompt} × {r.model}</span>
            {r.n > 0 ? <>
              <span className="text-[12px] tabular-nums text-slate-400">{r.correct}/{r.n}</span>
              <span className={`text-[12px] tabular-nums ${r.correct / r.n >= 0.85 ? 'text-good' : r.correct / r.n >= 0.7 ? 'text-slate-400' : 'text-bad'}`}>{Math.round(r.correct / r.n * 100)}%</span>
            </> : <span className="text-[11px] text-gold/80">adjudication cases only</span>}
          </div>
          <div className="flex gap-1">
            {archOrder.map(a => {
              const s = r.archetypes[a]
              if (!s) return <div key={a} className="flex-1 h-2 rounded-sm bg-white/5" />
              const frac = s.correct / s.n
              if (s.contested) return (
                <span key={a} className="tip flex-1">
                  <div className="h-2 rounded-sm bg-gold/60" style={{ backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(0,0,0,0.35) 3px, rgba(0,0,0,0.35) 6px)' }} />
                  <span className="tipbox">{a.replaceAll('_', ' ')} · CONTESTED, excluded from totals · agrees with written label {s.correct}/{s.n} · {s.contest_note}</span>
                </span>
              )
              return (
                <span key={a} className="tip flex-1">
                  <div className={`h-2 rounded-sm ${frac === 1 ? 'bg-good/70' : frac >= 0.5 ? 'bg-accent/60' : 'bg-bad/70'}`} />
                  <span className="tipbox">{a.replaceAll('_', ' ')}: {s.correct}/{s.n}</span>
                </span>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

function Results({ data, grid, onCase }) {
  return (
    <div className="flex flex-col gap-4">
      <Kpis data={data} grid={grid} />
      <div className="grid grid-cols-[1.6fr_1fr] gap-4">
        <LadderWalk grid={grid} data={data} />
        <Calibration data={data} />
      </div>
      <div className="grid grid-cols-[1fr_1.1fr] gap-4">
        <Heatmap data={data} />
        <PolicyGraph data={data} onCase={onCase} />
      </div>
      <Synthetic data={data} />
      <Frontier data={data} />
    </div>
  )
}

/* ------- playground: the queue, beat the model ------- */

// Fallback only: the live matrix ships in benchmark.json's meta block
// (single-sourced from engine/export.py's error_cost, audit 2026-08-24).
const FALLBACK_COST = { APPROVE: { APPROVE: 0, HOLD: 45, REJECT: 600 }, HOLD: { APPROVE: 45, HOLD: 0, REJECT: 600 }, REJECT: { APPROVE: 2000, HOLD: 500, REJECT: 0 } }
const AV_COLORS = ['#828fff', '#4ade80', '#cfa36c', '#f87171', '#38bdf8', '#c084fc']

function avatar(name) {
  const parts = (name || '?').split(/\s+/)
  const init = (parts[0]?.[0] || '') + (parts[1]?.[0] || '')
  let h = 0; for (const ch of name || '') h = (h * 31 + ch.charCodeAt(0)) % 997
  return { init: init.toUpperCase(), color: AV_COLORS[h % AV_COLORS.length] }
}

function Playground({ data, grid }) {
  const cellKey = 'v5|gemini-flash'
  const cell = grid.byKey[cellKey]
  // The adjudication queue: SYNTHETIC cases only, the simulation surface.
  // Uncontested archetypes test you against the construction label the same
  // way they test the models; the contested family is the real work: models
  // split and the policy underdetermines, so your call IS the routing
  // packet the feedback loop exists to collect. Contested cards score
  // nothing (there is no ground truth to price against).
  const playable = useMemo(() => {
    const entries = Object.entries(data.caseFiles || {})
      .filter(([id, f]) => f.json && !f.retired && f.kind === 'synthetic' && f.expected)
      .map(([id, f]) => {
        const run = cell?.cases.find(c => c.case_id === id && c.repeat_idx === 0)
          || data.cells.flatMap(c => c.model === 'gemini-flash' ? c.cases.filter(x => x.case_id === id && x.repeat_idx === 0) : [])[0]
        return { id, f, run, contested: !!f.contested }
      })
      .filter(x => x.run && x.run.decision)
    // stable shuffle by case-id hash so the deck order is varied but fixed
    return entries.sort((a, b) => {
      const h = s => { let v = 0; for (const ch of s) v = (v * 33 + ch.charCodeAt(0)) % 9973; return v }
      return h(a.id) - h(b.id)
    })
  }, [data, cell])
  const [idx, setIdx] = useState(0)
  const [picked, setPicked] = useState(null)   // your decision for the current card
  const [score, setScore] = useState({ you: 0, model: 0, done: 0 })
  const [calls, setCalls] = useState([])       // adjudication record for contested cards
  useEffect(() => {
    const onKey = e => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      const map = { a: 'APPROVE', h: 'HOLD', r: 'REJECT' }
      if (map[e.key] && !picked) decide(map[e.key])
      if ((e.key === 'Enter' || e.key === ' ') && picked) { e.preventDefault(); next() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
  if (!playable.length) return null
  const finished = score.done >= playable.length
  const cur = playable[Math.min(idx, playable.length - 1)]
  const j = cur.f.json
  const acct = j.account || {}
  const av = avatar(acct.owner_name || acct.business_name)
  const exposure = j.money?.at_risk_usd ?? 0
  const decide = d => {
    if (picked || finished) return
    setPicked(d)
    if (cur.contested) {
      setCalls(cs => [...cs, { case_id: cur.id, your_call: d, model: cur.run.decision, written_label: cur.f.expected }])
      setScore(s => ({ ...s, done: s.done + 1 }))
      return
    }
    setScore(s => ({
      you: s.you + (data.meta?.cost_matrix_usd || FALLBACK_COST)[cur.f.expected][d],
      model: s.model + (data.meta?.cost_matrix_usd || FALLBACK_COST)[cur.f.expected][cur.run.decision],
      done: s.done + 1,
    }))
  }
  const next = () => { setPicked(null); setIdx(i => i + 1) }
  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h2 className="text-3xl font-bold">The queue</h2>
          <p className="text-sm text-slate-400 max-w-xl">You are the reviewer, on the generated corpus the models were stress-tested with.
            Decide, then see what {cellKey.replace('|', ' × ')} did and what the written label says. Amber cards are the
            contested family: models split, the policy underdetermines, and your call is the adjudication.</p>
        </div>
        <div className="flex gap-6 text-right">
          <div><div className="text-2xl font-bold tabular-nums">${score.you.toLocaleString()}</div><Cap>your losses</Cap></div>
          <div><div className="text-2xl font-bold tabular-nums text-gold">${score.model.toLocaleString()}</div><Cap>model losses</Cap></div>
          <div><div className="text-2xl font-bold tabular-nums text-slate-500">{score.done}/{playable.length}</div><Cap>decided</Cap></div>
        </div>
      </div>
      <div className="flex gap-[2px] mb-4">
        {playable.map((c, i) => (
          <div key={c.id} className={`h-1 flex-1 rounded-full ${i < score.done ? 'bg-accent/70' : i === Math.min(idx, playable.length - 1) ? 'bg-slate-400' : 'bg-white/10'}`} />
        ))}
      </div>
      {finished && picked === null ? (
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="glass p-8 text-center">
          <div className="text-5xl font-bold mb-2">{score.you <= score.model ? 'You beat the model.' : 'The model beat you.'}</div>
          <p className="text-slate-400 mb-4">On the scored cards your decisions cost ${score.you.toLocaleString()} against the model's
            ${score.model.toLocaleString()} (construction labels price at $0 by definition). Refresh to run the queue again.</p>
          {calls.length > 0 && (
            <div className="text-left max-w-lg mx-auto">
              <Cap className="mb-2">your adjudications on the contested family</Cap>
              {calls.map(c => (
                <div key={c.case_id} className="text-[12px] text-slate-400 tabular-nums">
                  {c.case_id}: you {c.your_call} · model {c.model} · written label {c.written_label}
                </div>
              ))}
              <div className="flex items-center gap-3 mt-3">
                <CTA onClick={() => navigator.clipboard?.writeText(JSON.stringify({ adjudicated_at_view: true, calls }, null, 2)).catch(() => {})}>copy adjudication JSON</CTA>
                <span className="text-[11px] text-slate-600">paste into `python3 tools/ingest_annotations.py` to bank it in state/annotations.jsonl</span>
              </div>
            </div>
          )}
        </motion.div>
      ) : (
        <motion.div key={cur.id} initial={{ opacity: 0, y: 26, rotate: -0.6 }} animate={{ opacity: 1, y: 0, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 26 }}
          className={`glass p-6 ${cur.contested ? 'ring-1 ring-gold/40' : ''}`}>
          <div className="flex items-start gap-4 mb-5">
            <div className="w-12 h-12 rounded-full grid place-items-center text-lg font-bold shrink-0"
                 style={{ background: `${av.color}22`, color: av.color }}>{av.init}</div>
            <div className="min-w-0">
              <div className="text-[10px] tracking-[0.18em] text-slate-600 uppercase">{cur.id} · {j.flag_reason?.replaceAll('_', ' ').toLowerCase()}</div>
              <div className="text-xl font-semibold truncate">{acct.business_name || acct.owner_name}</div>
              <div className="text-xs text-slate-500">{acct.owner_name} · {acct.mcc ? `mcc ${acct.mcc} · ` : ''}{acct.tenure_days} days on platform</div>
            </div>
            <div className="ml-auto text-right shrink-0">
              <div className="text-3xl font-bold text-gold tabular-nums leading-none">${exposure.toLocaleString()}</div>
              <Cap className="mt-1">at risk now</Cap>
            </div>
          </div>
          {(() => {
            const txs = j.transactions || []
            const instruments = new Set(txs.map(x => x.instrument_last4).filter(Boolean)).size
            const declines = txs.filter(x => x.status === 'declined').length
            const transfers = txs.filter(x => (x.type || '').includes('transfer'))
            const biggest = Math.max(0, ...txs.map(x => x.amount_usd || 0))
            const hits = j.watchlist_hits || []
            const topHit = hits.slice().sort((a, b) => (b.score || 0) - (a.score || 0))[0]
            const priors = j.prior_cases || []
            const worstPrior = priors.find(pc => pc.decision === 'REJECT')
            const links = j.linked_accounts || []
            const badLink = links.find(l => l.status === 'CLOSED_FRAUD')
            const lastNote = (j.notes || []).slice(-1)[0]
            const rows = [
              ['verification', j.account?.verification?.status?.toLowerCase() || 'unknown',
               j.account?.verification?.status !== 'VERIFIED'],
              ['watchlist', hits.length
                ? `${hits.length} hit${hits.length > 1 ? 's' : ''} · ${topHit.match_type?.replaceAll('_', '+')} · score ${topHit.score}`
                : 'clear', hits.length > 0],
              ['prior record', priors.length
                ? `${priors.length} case${priors.length > 1 ? 's' : ''}${worstPrior ? ' · prior REJECT on record' : ''}`
                : 'none', !!worstPrior],
              ['linked accounts', links.length
                ? `${links.length} · ${badLink ? 'CLOSED_FRAUD link' : links[0].relationship?.replaceAll('_', ' ')}`
                : 'none', !!badLink],
              ['activity', txs.length
                ? `${txs.length} txns · ${instruments} instrument${instruments !== 1 ? 's' : ''} · ${declines} declined${transfers.length ? ` · ${transfers.length} payout transfer` : ''} · max $${biggest.toLocaleString()}`
                : 'none', declines > 3 || instruments > 6 || transfers.length > 0],
            ]
            return (
              <div className="mb-4 border-t border-white/5">
                {rows.map(([label, value, signal]) => (
                  <div key={label} className={`flex items-baseline justify-between py-2 border-b border-white/5 ${signal ? 'pl-2 border-l-2 border-l-gold/50' : 'pl-2 border-l-2 border-l-transparent'}`}>
                    <Cap>{label}</Cap>
                    <span className="text-[13px] text-slate-300 tabular-nums text-right">{value}</span>
                  </div>
                ))}
                {lastNote && (
                  <div className="py-2 pl-2 text-[12px] text-slate-500 italic border-b border-white/5">
                    "{lastNote.text.length > 150 ? lastNote.text.slice(0, 150) + '\u2026' : lastNote.text}"
                    <span className="not-italic text-slate-600"> · {lastNote.author}</span>
                  </div>
                )}
              </div>
            )
          })()}
          <details className="mb-4"><summary className="text-xs text-accent cursor-pointer">full case file</summary>
            <pre className="text-[10px] text-slate-500 max-h-[30vh] overflow-auto whitespace-pre-wrap mt-2">{JSON.stringify(j, null, 2)}</pre>
          </details>
          {!picked ? (
            <div className="flex gap-3 justify-center">
              {['APPROVE', 'HOLD', 'REJECT'].map(d => (
                <button key={d} onClick={() => decide(d)}
                  className={`px-8 py-2.5 rounded-full text-sm font-semibold transition-transform hover:scale-105 ${DC[d]}`}>
                  {d} <span className="ml-1.5 text-[10px] opacity-50 border border-current rounded px-1">{d[0]}</span>
                </button>
              ))}
            </div>
          ) : (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <div className="grid grid-cols-3 gap-3 text-center mb-3">
                {[['you', picked], ['the model', cur.run.decision],
                  [cur.contested ? 'written label (contested)' : 'the label', cur.f.expected]].map(([who, d]) => (
                  <div key={who} className={`rounded-xl py-3 ${cur.contested ? 'bg-gold/10' : d === cur.f.expected ? 'bg-good/10' : 'bg-bad/10'}`}>
                    <div className={`text-lg font-bold ${cur.contested ? 'text-gold' : d === cur.f.expected ? 'text-good' : 'text-bad'}`}>{d}</div>
                    <Cap>{who}{!cur.contested && d !== cur.f.expected ? ` · +$${(data.meta?.cost_matrix_usd || FALLBACK_COST)[cur.f.expected][d].toLocaleString()}` : ''}</Cap>
                  </div>
                ))}
              </div>
              {cur.contested && (
                <p className="text-[12px] text-gold/80 mb-3 text-center">No score on this card: the policy underdetermines it and your call is the adjudication being collected.</p>
              )}
              <p className="text-[13px] text-slate-400 leading-relaxed mb-4 max-h-28 overflow-auto">{cur.run.reasoning}</p>
              <div className="text-center">
                <CTA onClick={next}>{score.done >= playable.length ? 'see the verdict →' : 'next case →'}</CTA>
              </div>
            </motion.div>
          )}
        </motion.div>
      )}
    </div>
  )
}

/* ------- story ------- */

function Hero({ chip, title, children }) {
  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.4 }}
      className="min-h-[76vh] flex flex-col items-center justify-center text-center px-6">
      <div className="flex items-center gap-2.5 mb-5">
        <span className="text-[11px] font-semibold text-accent border border-accent/40 rounded-full px-2.5 py-0.5">{chip[0]}</span>
        <span className="text-[12px] text-slate-400 tracking-wide">{chip[1]}</span>
      </div>
      <h2 className="text-6xl font-bold tracking-tight mb-7 max-w-4xl leading-[1.08]">{title}</h2>
      {children}
    </motion.div>
  )
}

function Prose({ children }) {
  return <p className="text-slate-300 text-lg leading-8 max-w-2xl mx-auto mb-8">{children}</p>
}

function BigStat({ value, suffix = '', label, tone = 'text-gold', format }) {
  return (
    <div>
      <div className={`text-7xl font-bold leading-none tracking-tight ${tone}`}>
        <Num to={value} format={format || (v => Math.round(v))} />{suffix}
      </div>
      <Cap className="mt-2.5">{label}</Cap>
    </div>
  )
}

function CTA({ onClick, children }) {
  return <button onClick={onClick}
    className="text-slate-200 text-sm bg-white/[0.07] rounded-full px-4 py-1.5 hover:bg-white/[0.13] transition-colors">{children}</button>
}

const STEPS = [
  { chip: ['00', 'What this is'], title: <>A prompt is a <span className="text-gold">model release</span></>,
    render: (data, go) => (
      <div>
        <Prose>Every review team eventually delegates its checking to something cheaper than a person.
          This is a study of what happens when that something is a prompt: an agent reads a flagged
          merchant account and decides to approve, hold, or reject. The prompt behind it is versioned,
          benchmarked across eight models, attacked with planted instructions, and every claim it earns
          is priced in dollars and gated for trust before it is believed.</Prose>
        <div className="flex gap-3 justify-center">
          {[[`${data.meta?.total_runs ?? data.cells.reduce((a, c) => a + c.n, 0)}`, 'runs banked'],
            [`${[...new Set(data.cells.map(c => c.model))].length}`, 'models'],
            [`${Object.keys(data.caseFiles || {}).length}`, 'cases'],
            [`$${data.meta?.total_cost_usd_list ?? '–'}`, 'total API spend, list prices']].map(([v, l]) => (
            <div key={l} className="glass px-4 py-2.5"><b className="text-xl tabular-nums">{v}</b>
              <span className="text-[11px] text-slate-500 ml-2">{l}</span></div>
          ))}
        </div>
      </div>) },
  { chip: ['01', 'Problem'], title: <>Test the policy <span className="text-gold">before the prompt</span></>,
    render: (data, go) => (
      <div>
        <Prose>A grading suite inherits the blind spots of the policy it grades against. So before any
          prompt was scored, each clause of the policy was asked a simpler question: does a test for
          you exist at all? Two clauses had none, which means every earlier accuracy number was silent
          about them. Both are covered now, and the coverage is a checkable table, not a promise.</Prose>
        <div className="flex items-center gap-10 justify-center">
          <BigStat value={8} suffix="/8" label="policy clauses covered" />
          <CTA onClick={() => go('results')}>the policy graph →</CTA>
        </div>
      </div>) },
  { chip: ['02', 'Problem'],
    title: grid => <><span className="text-gold">{Math.round((grid.byKey['v1|gemini-flash']?.accuracy ?? 0.92) * 100)}%</span> with no policy at all</>,
    render: (data, go, grid) => {
      const v1 = grid.byKey['v1|gemini-flash'] || {}
      return (
        <div>
          <Prose>The naive baseline, a prompt containing no policy text whatsoever, decides most of
            the suite correctly. That is not good news about the model; it is bad news about
            accuracy as a measurement. What actually separates prompts is everything accuracy cannot
            see: whether output honors its contract, whether a decision survives being asked twice, and
            what each kind of error costs.</Prose>
          <div className="flex items-center gap-14 justify-center">
            <BigStat value={Math.round((v1.accuracy ?? 0) * 100)} suffix="%" label="naive accuracy" />
            <BigStat value={Math.round((v1.contract ?? 0) * 100)} suffix="%" label="its contract rate" tone="text-bad" />
            <CTA onClick={() => go('matrix', 'v1|gemini-flash')}>the cell →</CTA>
          </div>
        </div>)
    } },
  { chip: ['03', 'Plan'], title: <>One change <span className="text-gold">per rung</span></>,
    render: (data, go) => (
      <div>
        <Prose>A prompt that changes two things at once teaches nothing when the numbers move. Each
          rung of this ladder changes exactly one element, verified by machine diff, and every banked
          run is pinned to the exact text that produced it. Read in order, the ladder is an argument:
          quote the policy, then teach it, then harden the contract, one falsifiable step at a time.</Prose>
        <div className="flex items-center justify-center gap-0 mb-7">
          {ORDER.map((v, i) => (
            <div key={v} className="flex items-center">
              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: i * 0.07 }}
                className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold ${v === 'v5' ? 'border-gold text-gold shadow-[0_0_16px_rgba(240,168,72,0.4)]' : 'border-white/15 text-slate-300'}`}>{v}</motion.div>
              {i < ORDER.length - 1 && <div className="w-5 h-px bg-white/15" />}
            </div>
          ))}
        </div>
        <CTA onClick={() => go('ladder')}>open the ladder →</CTA>
      </div>) },
  { chip: ['04', 'Data'], title: <>Only <span className="text-gold">4 labels</span> are ground truth</>,
    render: (data, go) => (
      <div>
        <Prose>Four of these cases carry the expert's own answer. The rest were labeled by reasoning
          from the policy, and they say so on their face; the tiers are never averaged into one
          number. When five models split stably on a constructed case, the benchmark treats the split
          as evidence about the label and routes the case back to a human, which is what a feedback
          loop is for.</Prose>
        <div className="flex items-start gap-14 justify-center">
          <div className="flex flex-col gap-3">
            {(() => {
              const files = Object.values(data.caseFiles || {})
              const rows = [
                ['expert', files.filter(f => f.label_source === 'expert').length, 'bg-good'],
                ['adjudicated', files.filter(f => f.label_source === 'adjudicated').length, 'bg-accent'],
                ['constructed', files.filter(f => f.label_source === 'construction' && f.kind !== 'synthetic').length, 'bg-slate-600'],
                ['synthetic (generated)', files.filter(f => f.kind === 'synthetic').length, 'bg-slate-800'],
              ].filter(([, n]) => n > 0)
              const max = Math.max(...rows.map(([, n]) => n))
              return rows.map(([t, n, c], i) => (
                <div key={t} className="flex items-center gap-3">
                  <Cap className="w-36 text-right">{t}</Cap>
                  <motion.div className={`h-6 rounded ${c}`} initial={{ width: 0 }} animate={{ width: Math.max(n / max * 190, 8) }} transition={{ delay: 0.2 + i * 0.12 }} />
                  <span className="text-sm font-bold tabular-nums">{n}</span>
                </div>
              ))
            })()}
          </div>
          <CTA onClick={() => go('case', 'CASE-104')}>the disputed case →</CTA>
        </div>
      </div>) },
  { chip: ['05', 'Analysis'], title: <>A gated edit, <span className="text-gold">proven by repeats</span></>,
    render: (data, go, grid) => (
      <div>
        <Prose>The loop found flash reading an ownership change as a bust-out, six runs out of six.
          One sentence separating extraction from build-up fixed it. The gate first said revert,
          because an injection case appeared to regress; five repeats showed that regression was
          temperature noise, and the fix held four of four. The discipline, not the edit, is the
          finding.</Prose>
        <div className="flex items-center gap-14 justify-center">
          {(() => {
            const ch = grid.byKey[CHAMPION] || {}
            const suiteN = new Set((ch.cases || []).filter(c => SUITE.includes(c.kind)).map(c => c.case_id)).size
            return <>
              <BigStat value={Math.round((ch.accuracy ?? 0) * suiteN)} suffix={`/${suiteN}`} label="first pass, suite cases" />
              <BigStat value={ch.expected_loss_per_1k ?? 0} format={v => `$${Math.round(v)}`} label="expected loss per 1k" tone="text-gold" />
              <div>{ch.confusion && <MiniConf confusion={ch.confusion} />}</div>
              <CTA onClick={() => go('matrix', CHAMPION)}>the champion →</CTA>
            </>
          })()}
        </div>
      </div>) },
  { chip: ['06', 'Analysis'], title: <>The gate <span className="text-gold">polices headlines</span></>,
    render: (data, go, grid) => (
      <div>
        <Prose>qwen arrives at a perfect score, and the gate takes it away. Its twelve of twelve
          rests on a case that answers differently when asked twice, which makes the score first-run
          luck rather than a property of the model. A benchmark that cannot police its own headline
          numbers is an advertisement.</Prose>
        <div className="flex items-center gap-14 justify-center">
          <div>
            <div className="text-7xl font-bold leading-none text-slate-500 line-through decoration-bad decoration-4"><Num to={100} />%</div>
            <Cap className="mt-2.5">what qwen claims</Cap>
          </div>
          <BigStat value={grid.byKey['v4b|qwen3.8-max']?.flip ?? 0.5} format={v => v.toFixed(2)} label="its flip rate, asked twice" tone="text-bad" />
          <CTA onClick={() => go('matrix', 'v4b|qwen3.8-max')}>the gated cell →</CTA>
        </div>
      </div>) },
  { chip: ['07', 'Conclusion'], title: <>Ship <span className="text-gold">flash + v5</span>, and watch two things</>,
    render: (data, go, grid) => (
      <div className="text-left w-full">
        <Prose>Today's answer is flash with the gated prompt, at zero weighted loss under the stated
          prices. The honest remainder is written down: the prices themselves are assumptions with one
          partial grounding, no rung reliably resists a note planted by the account holder, stated
          confidence is decorative, and four expert labels bound everything at Wilson 0.51 to 1.00.</Prose>
        <Results data={data} grid={grid} onCase={id => go('case', id)} />
      </div>) },
]

/* ------- shell ------- */

export default function App() {
  const [data, setData] = useState(null)
  const [view, setView] = useState('story')
  const [open, setOpen] = useState(null)
  const [rung, setRung] = useState(null)
  const [caseId, setCaseId] = useState(null)
  const [step, setStep] = useState(0)
  const [auto, setAuto] = useState(true)
  useEffect(() => { fetch('/benchmark.json').then(r => r.json()).then(setData) }, [])

  // auto-advance: presentation walks itself; any manual move pauses it
  useEffect(() => {
    if (view !== 'story' || !auto) return
    if (step >= STEPS.length - 1) { setAuto(false); return }
    const t = setTimeout(() => setStep(s => Math.min(s + 1, STEPS.length - 1)), 16000)
    return () => clearTimeout(t)
  }, [view, auto, step])
  const grid = useMemo(() => {
    if (!data) return { prompts: [], models: [], byKey: {} }
    const prompts = [...new Set(data.cells.map(c => c.prompt))]
    const models = [...new Set(data.cells.map(c => c.model))].sort()
    const byKey = Object.fromEntries(data.cells.map(c => [`${c.prompt}|${c.model}`, c]))
    return { prompts, models, byKey }
  }, [data])

  useEffect(() => {
    const onKey = e => {
      if (view !== 'story') return
      if (e.key === 'ArrowRight') { setAuto(false); setStep(s => Math.min(s + 1, STEPS.length - 1)) }
      if (e.key === 'ArrowLeft') { setAuto(false); setStep(s => Math.max(s - 1, 0)) }
      if (e.key === ' ') { e.preventDefault(); setAuto(a => !a) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [view])

  if (!data) return <div className="p-10 text-slate-400">loading…</div>

  const go = (v, target) => {
    if (v === 'matrix' && target) { setOpen(grid.byKey[target] || null); setRung(null); setCaseId(null); setView('matrix') }
    else if (v === 'case') { setCaseId(target); setView('case') }
    else { setView(v); setCaseId(null) }
  }
  const s = STEPS[step]

  return (
    <div className="relative min-h-screen">
      <Aurora />
      <div className="relative z-10">
        <div style={{ background: '#08090c' }} className="border-b border-white/[0.04]">
        <header className="flex items-center gap-5 px-8 py-3.5 max-w-[1560px] mx-auto">
          <div className="flex items-center gap-2.5">
            {/* the mark is the ladder walk itself: a line stepping down to the lit endpoint (operator logo, docs/assets/logo.jpg) */}
            <svg width="26" height="24" viewBox="0 0 26 24" aria-hidden="true">
              <path d="M1 3 H10 L21 17 M6 9 H12" fill="none" stroke="#828fff" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="22" cy="19" r="3.4" fill="#cfe0ff" style={{ filter: 'drop-shadow(0 0 5px rgba(130,143,255,0.9))' }} />
            </svg>
            <h1 className="text-lg font-bold tracking-tight">verdict-bench</h1>
          </div>
          <span className="text-xs text-slate-600 hidden lg:block">a benchmark lab for a decisioning prompt</span>
          <a href="https://github.com/ShovalBenjer/verdict-bench" target="_blank" rel="noreferrer"
             className="ml-auto mr-3 flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors"
             title="source repository">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
            </svg>
            <span className="text-xs hidden md:block">ShovalBenjer/verdict-bench</span>
          </a>
          <nav className="flex glass !rounded-full p-1 text-sm">
            {[['story', 'Story'], ['matrix', 'Matrix'], ['ladder', 'Ladder'], ['results', 'Results'], ['play', 'Playground']].map(([v, l]) => (
              <button key={v} onClick={() => { setView(v); setCaseId(null); if (v !== 'matrix') { setOpen(null); setRung(null) } }}
                className={`px-4 py-1.5 rounded-full transition-colors ${view === v ? 'bg-accent/20 text-white' : 'text-slate-400 hover:text-white'}`}>{l}</button>
            ))}
          </nav>
        </header>
        </div>
        <div className="px-8 py-5 max-w-[1560px] mx-auto">

        {view === 'story' && (
          <>
            <AnimatePresence mode="wait">
              <Hero key={step} chip={s.chip} title={typeof s.title === 'function' ? s.title(grid) : s.title}>{s.render(data, go, grid)}</Hero>
            </AnimatePresence>
            <div className="fixed bottom-7 left-1/2 -translate-x-1/2 flex items-center gap-4 glass !rounded-full px-5 py-2.5 z-20">
              <button onClick={() => setAuto(a => !a)} title="space also toggles"
                className="text-accent text-sm w-5">{auto ? '❚❚' : '▶'}</button>
              <button onClick={() => { setAuto(false); setStep(Math.max(0, step - 1)) }} disabled={step === 0}
                className="text-accent disabled:opacity-25 text-lg">←</button>
              {STEPS.map((_, i) => (
                <button key={i} onClick={() => { setAuto(false); setStep(i) }}
                  className={`h-2 rounded-full transition-all overflow-hidden relative ${i === step ? 'bg-white/15 w-8' : 'bg-white/20 hover:bg-white/40 w-2'}`}>
                  {i === step && (
                    auto
                      ? <motion.span key={`p${step}`} className="absolute inset-y-0 left-0 bg-accent rounded-full"
                          initial={{ width: 0 }} animate={{ width: '100%' }} transition={{ duration: 16, ease: 'linear' }} />
                      : <span className="absolute inset-0 bg-accent rounded-full" />
                  )}
                </button>
              ))}
              <button onClick={() => { setAuto(false); setStep(Math.min(STEPS.length - 1, step + 1)) }} disabled={step === STEPS.length - 1}
                className="text-accent disabled:opacity-25 text-lg">→</button>
              <span className="text-[11px] text-slate-500 tabular-nums">{step + 1}/{STEPS.length}</span>
            </div>
          </>
        )}
        {view === 'matrix' && !caseId && <Matrix data={data} grid={grid} open={open} setOpen={setOpen} rung={rung} setRung={setRung}
          setCaseId={id => { setCaseId(id); setView('case') }} />}
        {view === 'case' && caseId && <CaseView caseId={caseId} data={data} onBack={() => { setView('matrix'); setCaseId(null) }} />}
        {view === 'ladder' && <LadderView data={data} />}
        {view === 'results' && <Results data={data} grid={grid} onCase={id => { setCaseId(id); setView('case') }} />}
        {view === 'play' && <Playground data={data} grid={grid} />}
        </div>
      </div>
    </div>
  )
}

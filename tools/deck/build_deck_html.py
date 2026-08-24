#!/usr/bin/env python3
"""Assemble the verdict-bench deck as a single-file HTML slide artifact.
Images inline as data URIs; numbers read from key_numbers.json."""
import base64
import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent.parent
DECK = ROOT / "docs" / "assets" / "deck"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DECK / "verdict-bench-deck.html"
K = json.loads((DECK / "key_numbers.json").read_text())


def uri(name, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode((DECK / name).read_bytes()).decode()


IMG = {n: uri(n) for n in ["eda_corpus.png", "injection_repeats.png", "reliability.png",
                           "synthetic_sweep.png", "population_sim.png", "holdout_funnel.png",
                           "bootstrap_loss.png"]}
INTUIT = "data:image/png;base64," + base64.b64encode(
    (DECK / "intuit-mark.png").read_bytes()).decode()

runs = K["generated_from_runs"]
cost = K["total_cost_usd_list"]
models = K["models"]
inj = K["injection_resistance_flash"]
trusted = K["trusted_cells"]
total_cells = K["total_cells"]

slides = []

slides.append(f"""
<section class="slide title-slide cover">
  <div class="marks marks-big">
    <span class="markpair"><svg width="86" height="80" viewBox="0 0 26 24"><path d="M1 3 H10 L21 17 M6 9 H12" fill="none" stroke="#828fff" stroke-width="2.2" stroke-linecap="round"/><circle cx="22" cy="19" r="3.4" fill="#cfe0ff" style="filter:drop-shadow(0 0 8px rgba(130,143,255,.9))"/></svg></span>
    <span class="x">&times;</span>
    <img class="intuit" src="{INTUIT}" alt="Intuit">
  </div>
  <h1>verdict&#8209;bench</h1>
  <div class="prepared">account&#8209;review decisioning prompt &middot; the Intuit case study</div>
  <div class="cover-byline">Shoval Benjer &middot; August 2026</div>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">Who is presenting</div>
  <h2>I run AI the way this benchmark runs prompts</h2>
  <p class="lead">Shoval Benjer, B.Sc. Data Science (Afeka, 2022&ndash;2025). Built an internal MCP layer of ~35 tools behind per&#8209;tool OAuth scopes, automated sales&#8209;call QC end to end (Arabic speech&#8209;to&#8209;text near 10% word error into a fifteen&#8209;layer score), and took a 900&#8209;agent productivity dashboard from a 17&#8209;second load to under a second.</p>
  <svg class=\"diagram\" viewBox=\"0 0 940 300\" role=\"img\" aria-label=\"operating loop\">\n    <defs><marker id=\"arr\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto-start-reverse\"><path d=\"M0 0 L10 5 L0 10 z\" fill=\"#828fff\"/></marker></defs>\n    <g font-family=\"Inter,sans-serif\" font-size=\"15\" text-anchor=\"middle\">\n      <rect x=\"20\" y=\"110\" width=\"150\" height=\"64\" rx=\"12\" fill=\"#111420\" stroke=\"#828fff\" stroke-width=\"1.4\"/>\n      <text x=\"95\" y=\"137\" fill=\"#e8ecf4\" font-weight=\"650\">operator</text><text x=\"95\" y=\"158\" fill=\"#8a93a3\" font-size=\"12\">frames the question</text>\n      <rect x=\"250\" y=\"110\" width=\"170\" height=\"64\" rx=\"12\" fill=\"#111420\" stroke=\"rgba(232,236,244,.25)\"/>\n      <text x=\"335\" y=\"137\" fill=\"#e8ecf4\" font-weight=\"650\">rules + claim controls</text><text x=\"335\" y=\"158\" fill=\"#8a93a3\" font-size=\"12\">what may be asserted</text>\n      <rect x=\"500\" y=\"110\" width=\"150\" height=\"64\" rx=\"12\" fill=\"#111420\" stroke=\"rgba(232,236,244,.25)\"/>\n      <text x=\"575\" y=\"137\" fill=\"#e8ecf4\" font-weight=\"650\">agents run</text><text x=\"575\" y=\"158\" fill=\"#8a93a3\" font-size=\"12\">every run recorded</text>\n      <rect x=\"730\" y=\"110\" width=\"180\" height=\"64\" rx=\"12\" fill=\"#111420\" stroke=\"#cfa36c\" stroke-width=\"1.4\"/>\n      <text x=\"820\" y=\"137\" fill=\"#e8ecf4\" font-weight=\"650\">evidence ledger</text><text x=\"820\" y=\"158\" fill=\"#8a93a3\" font-size=\"12\">sqlite + jsonl, append-only</text>\n      <rect x=\"380\" y=\"228\" width=\"200\" height=\"56\" rx=\"12\" fill=\"#111420\" stroke=\"#4ade80\" stroke-width=\"1.4\"/>\n      <text x=\"480\" y=\"251\" fill=\"#e8ecf4\" font-weight=\"650\">gates decide</text><text x=\"480\" y=\"270\" fill=\"#8a93a3\" font-size=\"12\">green ships, red blocks, no vibes</text>\n      <line x1=\"170\" y1=\"142\" x2=\"243\" y2=\"142\" stroke=\"#828fff\" stroke-width=\"1.6\" marker-end=\"url(#arr)\"/>\n      <line x1=\"420\" y1=\"142\" x2=\"493\" y2=\"142\" stroke=\"#828fff\" stroke-width=\"1.6\" marker-end=\"url(#arr)\"/>\n      <line x1=\"650\" y1=\"142\" x2=\"723\" y2=\"142\" stroke=\"#828fff\" stroke-width=\"1.6\" marker-end=\"url(#arr)\"/>\n      <path d=\"M 820 174 C 820 240, 640 256, 587 256\" fill=\"none\" stroke=\"#828fff\" stroke-width=\"1.6\" marker-end=\"url(#arr)\"/>\n      <path d=\"M 380 256 C 180 256, 95 230, 95 181\" fill=\"none\" stroke=\"#828fff\" stroke-width=\"1.6\" marker-end=\"url(#arr)\"/>\n    </g></svg>
  <p class="note">My standing setup runs on this loop: rules say what may be claimed, every run lands in a ledger, and gates decide what ships. verdict&#8209;bench is the same loop pointed at one prompt.</p>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">The study in three findings</div>
  <h2>What the ledger showed</h2>
  <ul class="verdicts">
    <li><b>The gate rejected my best fix.</b> v6 resisted 19 of 20 planted&#8209;instruction attacks, then missed the 12&#8209;of&#8209;12 decision bar it had pre&#8209;registered. It stays rejected.</li>
    <li><b>Generated cases separate models the visible nine cannot.</b> On 64 unseen cases the same prompt scores 100% on two models and 58% on the weakest.</li>
    <li><b>Contested cases are routed, not scored.</b> Where the policy text underdetermines the answer, no model is graded and the case goes to a human with the cross&#8209;model split attached.</li>
  </ul>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Problem</div>
  <h2>Accuracy is the wrong headline</h2>
  <div class="big-row">
    <div><div class="huge">92%</div><div class="cap">the NO-POLICY baseline's suite accuracy</div></div>
    <div><div class="huge">44&times;</div><div class="cap">cost spread across error types ($45 to $2,000)</div></div>
    <div><div class="huge">1</div><div class="cap">sanctions miss disqualifies, regardless of the rest</div></div>
  </div>
  <p class="note">Bottom line: the question is decision quality, not model quality. Which prompt&#8209;model pair do we trust, at what dollar loss, under which assumptions. That's the whole deck.</p>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">Scope, owned upfront</div>
  <h2>The two&#8209;hour version exists inside this one</h2>
  <p class="lead">Just to be clear, the two&#8209;hour version exists and I can point at it: the policy&#8209;teaching prompt plus the sanctions rule, 12&times;2 runs, three stated costs, one page. That's rungs v3 and v4 of my own ladder, and they carry most of the decision quality. I spent the rest of the time on one question the short version can't answer: how do I know when to trust it.</p>
  <p class="note gold-note">"The prompt took two hours. Knowing whether to trust it took the week, and the week is the part I would bring to the job."</p>
</section>""")


slides.append("""
<section class="slide">
  <div class="eyebrow">Measured, banked, and on no other slide</div>
  <h2>The work the deck does not show</h2>
  <ul class="commitments">
    <li><b>Classical baseline:</b> hand&#8209;featured logistic regression, leave&#8209;one&#8209;out 8/12 vs the LLM's 11&ndash;12/12; all four LR misses are policy&#8209;reasoning cases in the expensive direction.</li>
    <li><b>DSPy contrast arm:</b> a compiled prompt hits the same 12/12 ceiling with a structurally different artifact; kept as a comparison, not a rung.</li>
    <li><b>Self&#8209;consistency:</b> 11 of 12 cases unanimous over N=5 temperature&#8209;raised repeats; vote fraction is the earned&#8209;confidence instrument.</li>
    <li><b>Sequential test:</b> SPRT (p&#8320;=0.75, p&#8321;=0.92, &alpha;=0.05, &beta;=0.10) states how many more labeled cases certification needs before anyone promises one.</li>
    <li><b>Posterior odds:</b> beta&#8209;binomial puts the ladder's edge over v1 at ~3:1, reported as odds, not as a certainty.</li>
    <li><b>Provenance:</b> PaySim and ULB licenses verified at source; IEEE&#8209;CIS marked honestly unverifiable; fetch scripts print the exact manual steps.</li>
    <li><b>Surfaces:</b> a Tauri desktop shell, the adjudication&#8209;queue playground, and a number&#8209;grounding audit: 81&ndash;98% of v5's cited numbers trace to the case file.</li>
  </ul>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Plan</div>
  <h2>Six commitments, fixed before any analysis</h2>
  <ol class="commitments">
    <li><b>Suite separation.</b> Robustness kinds never blend into accuracy or loss.</li>
    <li><b>One change per rung,</b> machine&#8209;diffed, every run pinned by content hash.</li>
    <li><b>Repeats before belief.</b> N=5 before a single&#8209;run claim is trusted.</li>
    <li><b>Trust gates over headlines:</b> n, contract, CI width, flip, zero&#8209;tolerance tripwire.</li>
    <li><b>Dollar OEC:</b> three stated costs + one derived, swept, bootstrapped, reweighted.</li>
    <li><b>Label tiers visible:</b> 4 expert / 5 adjudicated / constructed, never averaged.</li>
  </ol>
</section>""")


slides.append("""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Plan &middot; the price of a mistake</div>
  <h2>How a mistake is priced</h2>
  <div class="mathgrid">
    <table class="costm">
      <tr><th></th><th>&rarr; APPROVE</th><th>&rarr; HOLD</th><th>&rarr; REJECT</th></tr>
      <tr><th>truth APPROVE</th><td class="zero">$0</td><td>$45</td><td>$600</td></tr>
      <tr><th>truth HOLD</th><td>$45</td><td class="zero">$0</td><td>$600</td></tr>
      <tr><th>truth REJECT</th><td class="hot">$2,000</td><td>$500</td><td class="zero">$0</td></tr>
    </table>
    <div class="maths">
      <p class="m">EL<sub>1k</sub> = (1000 / N) &Sigma;<sub>i</sub> (1/R) &Sigma;<sub>r</sub> C(y<sub>i</sub>, &ycirc;<sub>i,r</sub>)</p>
      <p class="mcap">mean over R repeats per case; an unparseable run is charged max<sub>&ycirc;</sub> C(y<sub>i</sub>, &ycirc;), never dropped</p>
      <p class="m">CI: case&#8209;clustered bootstrap, resample cases not runs, B=1,000, seed 1789</p>
      <p class="m">rankable only if Wilson 95% width &le; 0.5:&nbsp; p&#770; &plusmn; z&radic;(p&#770;(1&#8209;p&#770;)/n), z=1.96, n&ge;8</p>
      <p class="m">prevalence: EL(&pi;) = &pi;&middot;EL<sub>fraud</sub> + (1&#8209;&pi;)&middot;EL<sub>legit</sub>, &nbsp;&pi; swept 0.5% to 5%</p>
      <p class="m">queue cost<sub>1k</sub> = 1000 &middot; p<sub>HOLD</sub> &middot; $35 &nbsp;&mdash;&nbsp; a cautious prompt pays here, not in EL</p>
    </div>
  </div>
  <p class="note">Three costs stated, one derived ($500 = containment on a caught fraud); the $2,000 false&#8209;approve swept 1k to 5k without the ranking flipping. Accuracy weighs every mistake 1; this matrix is why the benchmark ranks on dollars.</p>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Plan &middot; the machine</div>
  <h2>One pipeline, every claim traceable to a run</h2>
  <svg class="diagram diagram-tall" viewBox="0 0 940 380" role="img" aria-label="system architecture">
    <defs><marker id="arr2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#828fff"/></marker></defs>
    <g font-family="Inter,sans-serif" font-size="14" text-anchor="middle">
      <rect x="20" y="40" width="170" height="60" rx="12" fill="#111420" stroke="rgba(232,236,244,.25)"/>
      <text x="105" y="65" fill="#e8ecf4" font-weight="650">89 labeled cases</text><text x="105" y="85" fill="#8a93a3" font-size="12">+ POLICY.md, frozen</text>
      <rect x="20" y="150" width="170" height="60" rx="12" fill="#111420" stroke="rgba(232,236,244,.25)"/>
      <text x="105" y="175" fill="#e8ecf4" font-weight="650">prompt ladder</text><text x="105" y="195" fill="#8a93a3" font-size="12">v1..v5, one change per rung</text>
      <rect x="270" y="95" width="170" height="60" rx="12" fill="#111420" stroke="#828fff" stroke-width="1.4"/>
      <text x="355" y="120" fill="#e8ecf4" font-weight="650">runner</text><text x="355" y="140" fill="#8a93a3" font-size="12">7 providers, N=5 repeats</text>
      <rect x="520" y="95" width="170" height="60" rx="12" fill="#111420" stroke="#cfa36c" stroke-width="1.4"/>
      <text x="605" y="120" fill="#e8ecf4" font-weight="650">sqlite ledger</text><text x="605" y="140" fill="#8a93a3" font-size="12">every run, hash-pinned</text>
      <rect x="270" y="240" width="170" height="60" rx="12" fill="#111420" stroke="#4ade80" stroke-width="1.4"/>
      <text x="355" y="265" fill="#e8ecf4" font-weight="650">trust gates</text><text x="355" y="285" fill="#8a93a3" font-size="12">n, contract, CI, flip, tripwire</text>
      <rect x="520" y="240" width="170" height="60" rx="12" fill="#111420" stroke="rgba(232,236,244,.25)"/>
      <text x="605" y="265" fill="#e8ecf4" font-weight="650">export</text><text x="605" y="285" fill="#8a93a3" font-size="12">benchmark.json, differential-tested</text>
      <rect x="760" y="150" width="160" height="90" rx="12" fill="#111420" stroke="rgba(232,236,244,.25)"/>
      <text x="840" y="178" fill="#e8ecf4" font-weight="650">surfaces</text><text x="840" y="198" fill="#8a93a3" font-size="12">site &middot; notebook</text><text x="840" y="216" fill="#8a93a3" font-size="12">deck &middot; this room</text>
      <line x1="190" y1="70" x2="263" y2="108" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr2)"/>
      <line x1="190" y1="180" x2="263" y2="142" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr2)"/>
      <line x1="440" y1="125" x2="513" y2="125" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr2)"/>
      <line x1="560" y1="155" x2="425" y2="235" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr2)"/>
      <line x1="440" y1="270" x2="513" y2="270" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr2)"/>
      <line x1="690" y1="270" x2="763" y2="222" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr2)"/>
      <line x1="690" y1="125" x2="763" y2="168" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr2)"/>
    </g></svg>
  <p class="note">The deck, the site, and the notebook all read the same export; the export mirrors the cost model exactly and a differential test proves it. No number on any surface has a second source.</p>
</section>""")

slides.append(f"""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Data</div>
  <h2>89 labeled cases, five suites, tiers kept apart</h2>
  <img src="{IMG['eda_corpus.png']}" alt="corpus EDA: cases by kind, labels by source, exposure distribution">
  <p class="note">Only 4 labels are expert ground truth; construction labels say so wherever they appear.</p>
</section>""")

slides.append(f"""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Analysis &middot; the ladder</div>
  <h2>Repeats dissolve stories</h2>
  <img src="{IMG['injection_repeats.png']}" alt="injection resistance by rung, all repeats">
  <p class="note">A single run showed v4b resisting the hardest planted note; N=5 put every shipped rung in one coin&#8209;flip band. The repeat protocol also reversed one gate decision and revoked one perfect score.</p>
</section>""")

slides.append(f"""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Analysis &middot; the matrix</div>
  <h2>The gate bites, and ranking survives</h2>
  <div class="big-row">
    <div><div class="huge">{total_cells}</div><div class="cap">prompt &times; model cells</div></div>
    <div><div class="huge gold">10</div><div class="cap">disqualified by the zero&#8209;tolerance tripwire</div></div>
    <div><div class="huge">{trusted}</div><div class="cap">fully trusted cells</div></div>
  </div>
  <img src="{IMG['bootstrap_loss.png']}" alt="case-clustered bootstrap of expected loss per cell">
  <p class="note">Weighted loss is the one OEC; contract, flip, injection, and the tripwire sit OUTSIDE it as guardrails, on purpose: fold them in and the score becomes gameable (decide APPROVE fast and confidently, and Goodhart wins). The gate fired ten times and the ranking survived; a gate that never fires is untested.</p>
</section>""")

slides.append(f"""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Analysis &middot; confidence</div>
  <h2>Stated confidence is decorative; earned confidence is measured</h2>
  <img src="{IMG['reliability.png']}" alt="stated vs earned confidence">
  <p class="note">All 21 stated confidences live between 0.90 and 1.00 while the runs earn 0.90 overall; at stated 0.90 the model was right once in two. The instrument that replaces it: vote fraction over N=5 temperature&#8209;raised repeats.</p>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Analysis &middot; the judge</div>
  <h2>Triangulated across three families</h2>
  <div class="judge-table">
    <div><span class="jname">gemini&#8209;flash</span><span class="jscore bad">5.0 / 5.0 / 5.0</span><span class="jnote">saturated: a dead instrument, reported as one</span></div>
    <div><span class="jname">claude&#8209;haiku</span><span class="jscore">4.2 / 3.9 / 3.1</span><span class="jnote">discriminates; proportionality lowest</span></div>
    <div><span class="jname">phi&#8209;4 (microsoft)</span><span class="jscore">4.6 / 5.0 / 4.7</span><span class="jnote">third family, overlaps no judged column</span></div>
  </div>
  <p class="note">Both discriminating families score proportionality lowest, the axis the policy makes hardest. The saturated judge is never averaged in.</p>
</section>""")

slides.append(f"""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Analysis &middot; scale</div>
  <h2>64 generated cases found a policy ambiguity</h2>
  <img src="{IMG['synthetic_sweep.png']}" alt="synthetic sweep by archetype">
  <p class="note">v5 sweeps the uncontested archetypes 48/48 (v1: 44/48). The contested family splits seven models 20&ndash;8 with no family pattern: the disagreement lives in the policy text, routed to its owner, never resolved by me.</p>
</section>""")


slides.append("""
<section class="slide">
  <div class="eyebrow">The question a 100% row earns</div>
  <h2>Is v5 overfit to nine cases? Three tests, one open risk</h2>
  <ul class="verdicts">
    <li><b>Transfer it never trained for:</b> v5 was tuned against gemini&#8209;flash only. Unchanged, it scores 12/12 on claude&#8209;sonnet and claude&#8209;haiku and 11/12 on gemini&#8209;pro (n=12 each). A prompt overfit to one model's reading does not transfer clean.</li>
    <li><b>Data authored after the freeze:</b> the 64 generated cases did not exist when v5 froze. It sweeps 56/56 on flash, 48/48 on qwen, 46/48 on gemini&#8209;pro. Overfit collapses on unseen data; this did not.</li>
    <li><b>The weak columns fail for capacity, not memorization:</b> llama trails at every rung, 8/12 on v1 before any tuning existed, 9/12 at v5 with contract 1.00. The ladder never bent toward its failures, and they predate it.</li>
    <li><b>And the discipline check:</b> v6 was rejected on its own pre&#8209;registered bar. An overfitting process chases the suite; this one turned down a better injection score for missing 12/12.</li>
    <li><b>Open, stated:</b> the true holdout is n=3 (v5: 2/3), too small to certify anything. That is exactly why the gates carry the ship claim and more expert labels is the named production blocker.</li>
  </ul>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Analysis &middot; the queue</div>
  <h2>A contested case is routed, not resolved</h2>
  <svg class="diagram diagram-tall" viewBox="0 0 940 330" role="img" aria-label="contested case routing">
    <defs><marker id="arr3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#828fff"/></marker></defs>
    <g font-family="Inter,sans-serif" font-size="14" text-anchor="middle">
      <rect x="20" y="120" width="180" height="64" rx="12" fill="#111420" stroke="rgba(232,236,244,.25)"/>
      <text x="110" y="147" fill="#e8ecf4" font-weight="650">data_quality_flag</text><text x="110" y="167" fill="#8a93a3" font-size="12">generated archetype, 28 runs</text>
      <rect x="280" y="120" width="180" height="64" rx="12" fill="#111420" stroke="#828fff" stroke-width="1.4"/>
      <text x="370" y="147" fill="#e8ecf4" font-weight="650">seven models</text><text x="370" y="167" fill="#8a93a3" font-size="12">split 20 HOLD / 8 REJECT</text>
      <rect x="540" y="40" width="180" height="64" rx="12" fill="#111420" stroke="#f87171" stroke-width="1.4"/>
      <text x="630" y="67" fill="#e8ecf4" font-weight="650">not a model error</text><text x="630" y="87" fill="#8a93a3" font-size="12">POLICY.md underdetermines it</text>
      <rect x="540" y="210" width="180" height="64" rx="12" fill="#111420" stroke="rgba(232,236,244,.25)"/>
      <text x="630" y="237" fill="#e8ecf4" font-weight="650">no score assigned</text><text x="630" y="257" fill="#8a93a3" font-size="12">contested flag in the ledger</text>
      <rect x="770" y="120" width="150" height="70" rx="12" fill="#111420" stroke="#cfa36c" stroke-width="1.4"/>
      <text x="845" y="147" fill="#e8ecf4" font-weight="650">policy owner</text><text x="845" y="167" fill="#8a93a3" font-size="12">gets the split, decides once</text>
      <line x1="200" y1="152" x2="273" y2="152" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr3)"/>
      <line x1="460" y1="134" x2="533" y2="82" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr3)"/>
      <line x1="460" y1="170" x2="533" y2="232" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr3)"/>
      <line x1="720" y1="72" x2="775" y2="122" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr3)"/>
      <line x1="720" y1="242" x2="775" y2="188" stroke="#828fff" stroke-width="1.6" marker-end="url(#arr3)"/>
    </g></svg>
  <p class="note">Same mechanism for sanctions&#8209;partial: zero APPROVEs in 23 runs across seven models, so it fails closed and ships contested. The benchmark's job on these cases is to surface the disagreement, not to pick a winner. Given time, this queue becomes a real reviewer surface; the playground already prototypes it.</p>
</section>""")

slides.append(f"""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Analysis &middot; population</div>
  <h2>A million-case simulation on measured kernels</h2>
  <img src="{IMG['population_sim.png']}" alt="population simulation, matrix vs exposure pricing">
  <p class="note">Behavior measured from the ledger; prevalence and exposure are named, swept assumptions. At 0.5% fraud, v1 costs $4,594/1k matrix&#8209;priced and $12,069/1k exposure&#8209;priced; rare large events dominate, exactly as the fraud literature says.</p>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">Adversarial reviews, answered with runs</div>
  <h2>The gate does not bend on deadline day</h2>
  <ul class="verdicts">
    <li><b>Refuted by probes:</b> precomputed&#8209;false is never exculpatory (4/4); the "you survive 108 by luck" perturbation HOLDs 4/4.</li>
    <li><b>Half right:</b> the sanctions middle case fails CLOSED, not open: zero APPROVEs in 23 runs across seven models; the verdict choice ships contested.</li>
    <li><b>v6, the injection line:</b> resists <b>19/20</b> where v5 sits at 5/9. I rejected it anyway: suite came back 11/12 against a bar I pre&#8209;registered at 12/12. It hurt, the bar stays, v6 ships as the named next rung.</li>
  </ul>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">PPDAC &middot; Conclusion</div>
  <h2>Ship v5 + gemini&#8209;flash, and say what that means</h2>
  <div class="ladder3">
    <div class="tier"><span class="tname good">CERTIFIED</span> gate recall 1.0 on every ranked cell; contract at floor everywhere ranked</div>
    <div class="tier"><span class="tname">SUGGESTED</span> 12/12 with Wilson floor 74%; holdout n=3; the ladder's edge at ~3:1 posterior odds</div>
    <div class="tier"><span class="tname bad">DECORATIVE</span> verbalized confidence; flash&#8209;as&#8209;judge</div>
  </div>
  <p class="note">Every number here triggers an action or it's just reporting: gates green means ship this pairing; a flip or contested split means hold and route to a human; a tripwire hit means roll back, no discussion. And the bar is purpose&#8209;graded: APPROVE needs less certainty at $0 exposure than HOLD does at $6k. The $0 is a point estimate; n=12 can't rule out ~$530k/1k worst&#8209;class. The gates carry the claim, not the zero.</p>
</section>""")


slides.append("""
<section class="slide">
  <div class="eyebrow">The boundary, drawn on purpose</div>
  <h2>Out of scope, and what I'd do next given time</h2>
  <div class="scope2">
    <div>
      <div class="scopehead">Deliberately out of scope</div>
      <ul class="commitments">
        <li><b>Tools and skills:</b> the agent decides from the dossier alone; no function calling, no retrieval. Adding tools changes the eval surface entirely, so it gets its own arm, not a patch.</li>
        <li><b>MCP integrations:</b> no external context servers; every input is the frozen case file, which is what keeps runs reproducible.</li>
        <li><b>CLI vs API surfaces:</b> the claude columns ride the subscription CLI (no sampler control, stated); the API/SDK rerun is specced and blocked only on a key.</li>
        <li><b>Memory attached to models:</b> every run is stateless by design. A remembering agent cannot be measured by repeats, and repeats are the method.</li>
        <li><b>Fine&#8209;tuning:</b> the prompt is the only movable part, on purpose.</li>
      </ul>
    </div>
    <div>
      <div class="scopehead gold">Next, given time, in order</div>
      <ul class="commitments">
        <li>More expert labels: the hard blocker; SPRT already says how many are needed.</li>
        <li>The v6 injection line through the full gate.</li>
        <li>API rerun of the claude columns with temperature control.</li>
        <li>The adjudication queue wired to a real reviewer; the playground already prototypes it.</li>
        <li>A tool&#8209;augmented variant as a new benchmark arm.</li>
      </ul>
    </div>
  </div>
</section>""")

slides.append("""
<section class="slide">
  <div class="eyebrow">If this shipped Monday</div>
  <h2>What breaks, in order</h2>
  <ol class="commitments">
    <li>Four real labels cannot certify a production prompt: more expert labels is the hard blocker.</li>
    <li>Pin the prompt AND the model: the pairing is what was verified.</li>
    <li>Injection is not solved by any shipped rung; the tested v6 line is next.</li>
    <li>Confidence gating must use vote fraction, never stated confidence.</li>
    <li>The contested case families need a policy&#8209;owner decision, and the queue collects it.</li>
  </ol>
  <p class="note">Readiness is four axes, not one: quality (gated), cost (priced per decision and per HOLD), reliability (latency, flip, self&#8209;consistency), safety (injection measured, fix tested, not shipped). I report all four or I'm not done.</p>
  <p class="note links">verdict&#8209;bench.pages.dev &middot; github.com/ShovalBenjer/verdict&#8209;bench</p>
</section>""")

n = len(slides)
html = f"""<title>verdict-bench deck</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;650;800&display=swap">
<style>
  :root {{
    --ink:#08090c; --panel:#111420; --line:rgba(232,236,244,.09);
    --text:#e8ecf4; --mut:#8a93a3; --dim:#5c6678;
    --accent:#828fff; --gold:#cfa36c; --good:#4ade80; --bad:#f87171;
  }}
  html,body {{ margin:0; background:var(--ink); color:var(--text);
    font-family:Inter,system-ui,sans-serif; }}
  .stage {{ height:100vh; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
  .slide {{ width:min(96vw, 170vh); aspect-ratio:16/9; box-sizing:border-box;
    padding:4.2% 5.5%; display:none; flex-direction:column; justify-content:center;
    background:radial-gradient(120% 90% at 12% -10%, rgba(61,71,184,.16), transparent 55%),
               radial-gradient(90% 70% at 95% 110%, rgba(107,83,48,.10), transparent 60%), var(--ink);
    border:1px solid var(--line); border-radius:18px; position:relative; }}
  .slide.on {{ display:flex; }}
  .eyebrow {{ font-size:12px; letter-spacing:.22em; text-transform:uppercase; color:var(--accent); margin-bottom:14px; }}
  h1 {{ font-size:clamp(48px,7vw,96px); font-weight:800; letter-spacing:-.02em; margin:12px 0 8px; text-wrap:balance; }}
  h2 {{ font-size:clamp(28px,3.4vw,46px); font-weight:800; letter-spacing:-.015em; margin:0 0 22px; max-width:26ch; text-wrap:balance; }}
  .thesis {{ font-size:clamp(17px,1.7vw,24px); color:var(--mut); margin:0 0 30px; }}
  .lead {{ font-size:clamp(16px,1.5vw,21px); line-height:1.55; color:var(--text); max-width:62ch; }}
  .note {{ font-size:clamp(13px,1.15vw,16px); line-height:1.55; color:var(--mut); max-width:70ch; margin-top:18px; }}
  .gold-note {{ color:var(--gold); font-size:clamp(15px,1.4vw,20px); }}
  .links {{ color:var(--dim); letter-spacing:.04em; }}
  .intro {{ font-size:clamp(15px,1.5vw,20px); line-height:1.6; color:var(--mut);
    max-width:58ch; }}
  .intro b {{ color:var(--text); }}
  .big-row {{ display:flex; gap:6%; margin:8px 0 4px; }}
  .huge {{ font-size:clamp(44px,6vw,86px); font-weight:800; letter-spacing:-.02em;
    font-variant-numeric:tabular-nums; line-height:1; }}
  .huge.gold {{ color:var(--gold); }}
  .cap {{ font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--dim); margin-top:10px; max-width:22ch; line-height:1.5; }}
  .commitments {{ margin:0; padding-left:1.2em; display:flex; flex-direction:column; gap:10px;
    font-size:clamp(14px,1.35vw,19px); line-height:1.5; color:var(--mut); max-width:75ch; }}
  .commitments b {{ color:var(--text); }}
  .verdicts {{ margin:0; padding-left:1.1em; display:flex; flex-direction:column; gap:16px;
    font-size:clamp(14px,1.4vw,20px); line-height:1.55; color:var(--mut); max-width:78ch; }}
  .verdicts b {{ color:var(--text); }}
  img {{ max-width:100%; max-height:52%; object-fit:contain; border-radius:10px; background:#fff; align-self:flex-start; }}
  .judge-table {{ display:flex; flex-direction:column; gap:0; border-top:1px solid var(--line); margin-top:6px; }}
  .judge-table > div {{ display:grid; grid-template-columns:220px 190px 1fr; gap:18px; align-items:baseline;
    padding:16px 4px; border-bottom:1px solid var(--line); }}
  .jname {{ font-weight:650; }}
  .jscore {{ font-variant-numeric:tabular-nums; font-weight:650; color:var(--good); }}
  .jscore.bad {{ color:var(--bad); }}
  .jnote {{ color:var(--mut); font-size:15px; }}
  .ladder3 {{ display:flex; flex-direction:column; gap:14px; margin-top:6px; }}
  .tier {{ border:1px solid var(--line); background:var(--panel); border-radius:12px;
    padding:16px 20px; font-size:clamp(14px,1.3vw,18px); color:var(--mut); line-height:1.5; }}
  .tname {{ display:inline-block; min-width:120px; font-size:12px; letter-spacing:.18em; font-weight:650; color:var(--accent); }}
  .tname.good {{ color:var(--good); }}
  .tname.bad {{ color:var(--bad); }}
  .title-slide {{ align-items:flex-start; }}
  .cover {{ justify-content:center; }}
  .cover h1 {{ font-size:clamp(64px,9vw,128px); }}
  .cover-byline {{ font-size:15px; color:var(--mut); letter-spacing:.08em; margin-top:26px; }}
  .marks-big {{ margin-bottom:26px; }}
  .marks-big .intuit {{ height:44px; }}
  .diagram {{ width:100%; max-height:44%; }}
  .scope2 {{ display:grid; grid-template-columns:1fr 1fr; gap:5%; margin-top:4px; }}
  .scopehead {{ font-size:12px; letter-spacing:.18em; text-transform:uppercase; color:var(--accent); margin-bottom:12px; font-weight:650; }}
  .scopehead.gold {{ color:var(--gold); }}
  .mathgrid {{ display:grid; grid-template-columns:auto 1fr; gap:4%; align-items:start; margin-top:6px; }}
  .costm {{ border-collapse:collapse; font-variant-numeric:tabular-nums; }}
  .costm th, .costm td {{ border:1px solid var(--line); padding:10px 16px; font-size:clamp(12px,1.15vw,16px); text-align:right; }}
  .costm th {{ color:var(--dim); font-weight:650; text-transform:uppercase; font-size:11px; letter-spacing:.08em; }}
  .costm td.zero {{ color:var(--dim); }}
  .costm td.hot {{ color:var(--gold); font-weight:800; }}
  .maths {{ display:flex; flex-direction:column; gap:9px; }}
  .m {{ margin:0; font-size:clamp(13px,1.25vw,17px); color:var(--text); font-variant-numeric:tabular-nums; }}
  .mcap {{ margin:0; font-size:clamp(11px,1vw,13px); color:var(--dim); }}
  .diagram-tall {{ max-height:56%; }}
  .marks {{ display:flex; align-items:center; gap:22px; margin-bottom:10px; }}
  .marks .x {{ color:var(--dim); font-size:20px; }}
  .marks .intuit {{ height:34px; width:auto; max-height:none; background:none; border-radius:0; filter:brightness(1.35) saturate(1.05); }}
  .prepared {{ font-size:13px; letter-spacing:.16em; text-transform:uppercase; color:var(--dim); margin:2px 0 16px; }}
  .rail {{ position:fixed; bottom:22px; left:50%; transform:translateX(-50%);
    display:flex; gap:7px; align-items:center; background:rgba(17,20,28,.8);
    border:1px solid var(--line); border-radius:999px; padding:9px 16px; }}
  .rail .dot {{ width:7px; height:7px; border-radius:50%; background:rgba(232,236,244,.18); cursor:pointer; border:none; padding:0; }}
  .rail .dot.on {{ background:var(--accent); }}
  .rail .count {{ font-size:12px; color:var(--dim); margin-left:8px; font-variant-numeric:tabular-nums; }}
  .hint {{ position:fixed; top:20px; right:26px; font-size:12px; color:var(--dim); letter-spacing:.06em; }}
  button:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
  @media (prefers-reduced-motion: no-preference) {{
    .slide.on {{ animation:in .35s ease; }}
    @keyframes in {{ from {{ opacity:0; transform:translateY(10px);}} to {{ opacity:1; transform:none;}} }}
  }}
</style>
<div class="stage">
{''.join(slides)}
</div>
<div class="hint">&larr; &rarr; keys &middot; click dots</div>
<div class="rail" id="rail"></div>
<script>
  const slides = [...document.querySelectorAll('.slide')];
  const rail = document.getElementById('rail');
  let i = 0;
  slides.forEach((_, k) => {{
    const b = document.createElement('button');
    b.className = 'dot'; b.setAttribute('aria-label', 'slide ' + (k+1));
    b.onclick = () => show(k); rail.appendChild(b);
  }});
  const count = document.createElement('span');
  count.className = 'count'; rail.appendChild(count);
  function show(k) {{
    i = Math.max(0, Math.min(slides.length - 1, k));
    slides.forEach((s, j) => s.classList.toggle('on', j === i));
    [...rail.querySelectorAll('.dot')].forEach((d, j) => d.classList.toggle('on', j === i));
    count.textContent = (i+1) + ' / ' + slides.length;
  }}
  addEventListener('keydown', e => {{
    if (e.key === 'ArrowRight' || e.key === ' ') show(i+1);
    if (e.key === 'ArrowLeft') show(i-1);
  }});
  show(0);
</script>
"""
OUT.write_text(html)
print(f"deck html: {n} slides, {len(html)//1024} KB (images inline)")

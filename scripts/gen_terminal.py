"""Generate assets/terminal.svg: a looping macOS-style terminal that types commands.

Run: python3 scripts/gen_terminal.py
"""

from pathlib import Path
from xml.sax.saxutils import escape

# (kind, text): 'cmd' lines are typed char by char, 'out' lines pop in instantly
LINES = [
    ('cmd', 'whoami'),
    ('out', 'Bao Trieu — Backend Engineer @ Piggi'),
    ('cmd', 'cat stack.txt'),
    ('out', 'Go · GraphQL · MySQL · NestJS · Redis · RabbitMQ · K8s'),
    ('cmd', 'ls side-quests/'),
    ('out', 'reverse-engineering/  n8n-automation/  coffee.log'),
    ('cmd', 'echo $MOTTO'),
    ('out', 'Clean over clever. Ship it, then refactor. ✨'),
]

WIDTH = 720
FONT_SIZE = 15
CHAR_WIDTH = 9.1  # approx advance of a 15px monospace glyph
LINE_HEIGHT = 26
TOP_PADDING = 64
LEFT_PADDING = 24
PROMPT = '❯ '
PROMPT_WIDTH = 2 * CHAR_WIDTH

TYPE_SECONDS_PER_CHAR = 0.08
PAUSE_AFTER_CMD = 0.35
PAUSE_AFTER_OUT = 0.6
HOLD_AT_END = 4.0

COLORS = {
    'bg': '#1a1b27',
    'bar': '#24253a',
    'prompt': '#ff6ea8',
    'cmd': '#f8f8f2',
    'out': '#7ee8fa',
    'cursor': '#ffd166',
}


def build_timeline():
    """Return per-line (start, end) seconds and the total loop duration."""
    timeline = []
    clock = 0.5
    for kind, text in LINES:
        if kind == 'cmd':
            duration = len(text) * TYPE_SECONDS_PER_CHAR
            timeline.append((clock, clock + duration))
            clock += duration + PAUSE_AFTER_CMD
            continue
        timeline.append((clock, clock))
        clock += PAUSE_AFTER_OUT
    return timeline, clock + HOLD_AT_END


def pct(seconds, total):
    return f'{seconds / total * 100:.3f}%'


def render():
    timeline, total = build_timeline()
    height = TOP_PADDING + LINE_HEIGHT * (len(LINES) + 1) + 8
    styles = []
    body = []

    for index, ((kind, text), (start, end)) in enumerate(zip(LINES, timeline)):
        y = TOP_PADDING + index * LINE_HEIGHT
        group_id = f'l{index}'
        # Whole line (prompt included) stays hidden until its turn
        styles.append(
            f'@keyframes show{index}{{0%,{pct(start, total)}{{opacity:0}}'
            f'{pct(start + 0.001, total)},100%{{opacity:1}}}}'
            f'#{group_id}{{animation:show{index} {total:.2f}s infinite}}'
        )
        if kind == 'out':
            body.append(
                f'<g id="{group_id}"><text x="{LEFT_PADDING}" y="{y}" class="out">{escape(text)}</text></g>'
            )
            continue

        text_x = LEFT_PADDING + PROMPT_WIDTH
        text_width = len(text) * CHAR_WIDTH
        cover_id = f'c{index}'
        # A background-colored rect slides right in steps, revealing one char at a time
        styles.append(
            f'@keyframes type{index}{{0%,{pct(start, total)}{{transform:translateX(0)}}'
            f'{pct(end, total)},100%{{transform:translateX({text_width + CHAR_WIDTH:.1f}px)}}}}'
            f'#{cover_id}{{animation:type{index} {total:.2f}s infinite;'
            f'animation-timing-function:steps({len(text) + 1},end)}}'
        )
        body.append(
            f'<g id="{group_id}">'
            f'<text x="{LEFT_PADDING}" y="{y}" class="prompt">{escape(PROMPT)}</text>'
            f'<text x="{text_x}" y="{y}" class="cmd">{escape(text)}</text>'
            f'<rect id="{cover_id}" x="{text_x}" y="{y - FONT_SIZE}" width="{text_width + CHAR_WIDTH:.1f}" '
            f'height="{LINE_HEIGHT}" fill="{COLORS["bg"]}"/>'
            f'</g>'
        )

    last_y = TOP_PADDING + len(LINES) * LINE_HEIGHT
    last_start = timeline[-1][1] + PAUSE_AFTER_OUT
    styles.append(
        f'@keyframes showEnd{{0%,{pct(last_start, total)}{{opacity:0}}'
        f'{pct(last_start + 0.001, total)},100%{{opacity:1}}}}'
        f'#end{{animation:showEnd {total:.2f}s infinite}}'
        '@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}'
        '#cursor{animation:blink 1s step-end infinite}'
    )
    body.append(
        f'<g id="end"><text x="{LEFT_PADDING}" y="{last_y}" class="prompt">{escape(PROMPT)}</text>'
        f'<rect id="cursor" x="{LEFT_PADDING + PROMPT_WIDTH}" y="{last_y - FONT_SIZE + 2}" '
        f'width="{CHAR_WIDTH:.1f}" height="{FONT_SIZE + 2}" fill="{COLORS["cursor"]}"/></g>'
    )

    css = (
        f'text{{font-family:"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;font-size:{FONT_SIZE}px;'
        f'white-space:pre}}'
        f'.prompt{{fill:{COLORS["prompt"]};font-weight:700}}.cmd{{fill:{COLORS["cmd"]}}}'
        f'.out{{fill:{COLORS["out"]}}}.title{{fill:#8b8fa8;font-size:13px}}'
        + ''.join(styles)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<style>{css}</style>
<rect width="{WIDTH}" height="{height}" rx="12" fill="{COLORS["bg"]}"/>
<path d="M0 12a12 12 0 0 1 12-12h{WIDTH - 24}a12 12 0 0 1 12 12v24H0z" fill="{COLORS["bar"]}"/>
<circle cx="22" cy="18" r="6" fill="#ff5f57"/><circle cx="42" cy="18" r="6" fill="#febc2e"/><circle cx="62" cy="18" r="6" fill="#28c840"/>
<text x="{WIDTH / 2}" y="23" text-anchor="middle" class="title">bao@piggi: ~</text>
{''.join(body)}
</svg>
'''


if __name__ == '__main__':
    output_path = Path(__file__).resolve().parent.parent / 'assets' / 'terminal.svg'
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(render(), encoding='utf-8')
    print(f'Wrote {output_path}')

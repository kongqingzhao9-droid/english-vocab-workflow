"""Extract the agreed purple/green/red markings; keep page renders for visual/OCR checks."""
import argparse
import json
import sys
from pathlib import Path
import pymupdf


def purple(r, g, b):
    return b > 230 and r > 175 and 150 < g < 225 and b - g > 35 and r - g > 8


def green(r, g, b):
    return g > r + 20 and g > b + 20 and g > 180


def red(r, g, b):
    return r > 120 and r - g > 80 and r - b > 80


def ratio(pixels, width, height, channels, scale, box, predicate):
    x0, y0, x1, y1 = box
    hit = total = 0
    for y in range(max(0, int(y0 * scale)), min(height, int(y1 * scale))):
        for x in range(max(0, int(x0 * scale)), min(width, int(x1 * scale))):
            i = (y * width + x) * channels
            hit += bool(predicate(*pixels[i:i + 3])); total += 1
    return hit / total if total else 0


def extract(pdf, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pages = []
    with pymupdf.open(pdf) as document:
        if document.needs_pass:
            raise ValueError('PDF is password protected; export a readable copy.')
        for index, page in enumerate(document):
            scale = 3.0
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
            pixels = pix.samples
            def color(box, predicate):
                return ratio(pixels, pix.width, pix.height, pix.n, scale, box, predicate)
            words = page.get_text('words')
            lines = []
            for word in sorted(words, key=lambda z: (z[1] + z[3]) / 2):
                cy = (word[1] + word[3]) / 2
                for line in lines:
                    if abs(line['y'] - cy) < 6:
                        line['words'].append(word); break
                else:
                    lines.append({'y': cy, 'words': [word]})
            marked, phrases, red_lines = [], [], []
            for line in sorted(lines, key=lambda x: x['y']):
                line['words'].sort(key=lambda z: z[0])
                run = []
                for word in line['words']:
                    text = word[4].strip('.,;:\'"()!?- ')
                    if color(word[:4], purple) > .25 and text:
                        marked.append(text)
                    if color(word[:4], green) > .25 and text:
                        run.append(text)
                    elif run:
                        phrases.append(' '.join(run)); run = []
                if run:
                    phrases.append(' '.join(run))
                x0 = min(w[0] for w in line['words']); x1 = max(w[2] for w in line['words'])
                y1 = max(w[3] for w in line['words'])
                if color((x0, y1, x1, y1 + 10), red) > .02:
                    red_lines.append(line)
            sentences, current = [], []
            for line in red_lines:
                if current and line['y'] - current[-1]['y'] >= 22:
                    sentences.append(' '.join(w[4] for ln in current for w in ln['words'])); current = []
                current.append(line)
            if current:
                sentences.append(' '.join(w[4] for ln in current for w in ln['words']))
            image = output / f'page-{index + 1:03}.png'
            pix.save(str(image))
            pages.append({'page': index + 1, 'vocab': list(dict.fromkeys(marked)),
                          'phrases': phrases, 'sentences': sentences,
                          'text': page.get_text(), 'render': str(image.resolve()),
                          'needs_ocr': not bool(words),
                          'review_required': 'Compare this page render with extracted markings; text layers can omit individual words.'})
    result = {'file': str(Path(pdf).resolve()), 'pages': pages}
    (output / 'extraction.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Extraction and page renders saved to:', output.resolve())
    print('Visual verification is required before committing the batch. Use OCR for missing text; do not treat missing text as no markings.')
    return result


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf'); parser.add_argument('--out', required=True)
    args = parser.parse_args()
    extract(args.pdf, args.out)

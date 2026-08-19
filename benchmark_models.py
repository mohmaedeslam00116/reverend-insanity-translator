import sys
import time
import json
from pathlib import Path
import requests

from config import Config
from prompt_templates import LITERARY_SYSTEM_PROMPT

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Free models to benchmark
CANDIDATE_MODELS = [
    "stepfun/step-3.7-flash:free",
    "tencent/hy3:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "kilo-auto/free",
    "openrouter/free",
    "dots-studio/dots-3-note-preview:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
]

TEST_EXCERPT = """Chapter 1 - 1: The heart of a demon never has regret even in death

"Fang Yuan, quietly hand over the Spring Autumn Cicada and I'll give you a quick death!"

"Old bastard Fang, stop resisting! Today all the righteous factions have united to destroy your demonic stronghold. This place is already laid with inescapable traps; you have nowhere to run!"

"Demon Fang Yuan, just to refine the Spring Autumn Cicada, you slaughtered millions of innocent souls. Your sins are unforgivable and utterly monstrous!"

"300 years ago you defiled me, exterminated my entire clan down to nine generations. From that day on, I swore with burning hatred to tear you to pieces! Today, you shall die!"

Fang Yuan wore ragged deep green robes, his long hair disheveled and his body soaked in blood. He looked calmly around him. The bloodstained cloth flapped in the mountain wind like a tattered battle flag. Fresh blood seeped from countless wounds; beneath his feet, a deep pool of crimson had already gathered.

He understood his situation with crystal clarity. Yet even in the face of certain demise, his expression remained tranquil. His eyes were like ancient, fathomless wells, reflecting neither fear nor regret.

Gazing at the blood-red sunset over the horizon, Fang Yuan smiled softly and chanted:
"The setting sun descends over emerald peaks, the autumn moon drifts with the spring breeze.
Youthful hair like dark silk turns to white snow in an instant;
Whether triumph or failure, looking back, all is but fleeting smoke."

"If the Spring Autumn Cicada I refined truly works... in my next life, I shall still walk the Demonic Path!"
With a loud roar of laughter, a blinding, apocalyptic light burst from his body."""

headers = Config.get_api_headers()

results = []

print("=" * 80)
print("🚀 بدء اختبار ومقارنة النماذج المجانية المتاحة على Kilo AI Gateway")
print("=" * 80)

for idx, model in enumerate(CANDIDATE_MODELS, 1):
    print(f"\n[{idx}/{len(CANDIDATE_MODELS)}] اختبار النموذج: {model} ...", flush=True)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": LITERARY_SYSTEM_PROMPT},
            {"role": "user", "content": f"ترجم النص التالي إلى العربية الفصحى الأدبية الرفيعة:\n\n{TEST_EXCERPT}"}
        ],
        "temperature": 0.5,
    }

    start_t = time.time()
    try:
        r = requests.post(
            Config.KILO_API_URL,
            headers=headers,
            json=payload,
            timeout=45,
        )
        elapsed = time.time() - start_t

        if r.status_code == 200:
            res_data = r.json()
            choices = res_data.get("choices", [])
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "").strip()
                print(f"  [✓] نجح في {elapsed:.2f} ثانية | عدد الأحرف: {len(content)}")
                results.append({
                    "model": model,
                    "status": "success",
                    "latency": round(elapsed, 2),
                    "translation": content,
                    "length": len(content),
                })
            else:
                print(f"  [X] تنسيق استجابة غير صالح: {r.text[:200]}")
                results.append({
                    "model": model,
                    "status": "error",
                    "error": f"Invalid format: {r.text[:200]}",
                    "latency": round(elapsed, 2),
                })
        else:
            print(f"  [X] فشل الاستجابة: HTTP {r.status_code} - {r.text[:200]}")
            results.append({
                "model": model,
                "status": "error",
                "error": f"HTTP {r.status_code}: {r.text[:200]}",
                "latency": round(elapsed, 2),
            })
    except Exception as e:
        elapsed = time.time() - start_t
        print(f"  [X] خطأ/استثناء: {e}")
        results.append({
            "model": model,
            "status": "error",
            "error": str(e),
            "latency": round(elapsed, 2),
        })
    
    # Short delay between model requests
    time.sleep(2)

# Save results to json for detailed inspection
out_json = Config.OUTPUT_DIR / "model_comparison_results.json"
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 80)
print(f"تم حفظ النتائج بالكامل في: {out_json}")
print("=" * 80)

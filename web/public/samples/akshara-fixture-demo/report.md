# AksharaCheck report: 127.0.0.1:49205/index.html

3 problems to fix, 6 things to check and 2 notes.

Page: http://127.0.0.1:49205/index.html

BharatCode qwen-3.8-27b explained 9 of the 9 findings to fix or check (6 model calls, 3,953 tokens, 1 min 39 s). 3 explanations come from an earlier run; their fixes were tested again in Chromium.

## To fix

### Fix: Broken letters

> यह एक मााित्रा त्रुटि का परीक्षण है

- मााि `U+092E U+093E U+093E U+093F`: A vowel sign with no letter before it

BharatCode: This Devanagari text contains broken character sequences that render as strange, malformed letters. Please fix the underlying text by removing the stray vowel signs so each vowel follows its consonant.
हिंदी: इस हिंदी टेक्स्ट में गलत अक्षर संयोजन हैं जिससे शब्द बिगड़े हुए दिख रहे हैं, कृपया इसे सही करें।
ಕನ್ನಡ: ಈ ಹಿಂದಿ ಪಠ್ಯದಲ್ಲಿ ತಪ್ಪು ಅಕ್ಷರ ಸಂಯೋಜನೆಗಳಿವೆ, ದಯವಿಟ್ಟು ಸರಿಪಡಿಸಿ.

What to change: Correct the text itself. This is a typing or conversion mistake, so CSS cannot repair it.

Page: http://127.0.0.1:49205/index.html

### Fix: Broken letters

> ಇದು ಕಾಿ ತಪ್ಪಾದ ಗುರುತುಗಳ ಪರೀಕ್ಷೆ

- ಕಾಿ `U+0C95 U+0CBE U+0CBF`: A vowel sign with no letter before it

BharatCode: The Kannada text has a stray vowel mark with no consonant to attach to, making the word unreadable. Fix the typo by either removing the extra mark or restoring the missing consonant, and check the text in Kannada script.
हिंदी: कन्नड़ पाठ में एक अतिरिक्त स्वर चिह्न है जिसे हटाना या उसके आगे सही व्यंजन जोड़ना चाहिए।
ಕನ್ನಡ: ಕನ್ನಡ ಪಠ್ಯದಲ್ಲಿ ಅನಗತ್ಯ ಸ್ವರ ಚಿಹ್ನೆ ಇದೆ, ಅದನ್ನು ತೆಗೆದುಹಾಕಿ ಅಥವಾ ಸರಿಯಾದ ವ್ಯಂಜನವನ್ನು ಸೇರಿಸಿ.

What to change: Correct the text itself. This is a typing or conversion mistake, so CSS cannot repair it.

Page: http://127.0.0.1:49205/index.html

### Fix: Web font did not load

The font file returned HTTP 404.


BharatCode: A custom font file the page tries to load is missing, so the browser falls back to a default font. Either fix the font path so it points to a file that exists, or remove the font reference so the page uses its default typeface.
हिंदी: पेज पर इस्तेमाल होने वाला कस्टम फ़ॉन्ट फ़ाइल मौजूद नहीं है, इसलिए या तो फ़ाइल का सही पता लगाएँ या फ़ॉन्ट को हटा दें।
ಕನ್ನಡ: ಪುಟದಲ್ಲಿ ಬಳಸಲಾಗುತ್ತಿರುವ ಕಸ್ಟಮ್ ಫಾಂಟ್ ಕಡತ ಲಭ್ಯವಿಲ್ಲ, ಆದ್ದರಿಂದ ಫಾಂಟ್ ವಿಳಾಸವನ್ನು ಸರಿಪಡಿಸಿ ಅಥವಾ ಅದನ್ನು ತೆಗೆದುಹಾಕಿ.

What to change: Check the font address, and whether that font is actually used for visible text.

Page: http://127.0.0.1:49205/index.html

## To check

### Check: Two languages without labels

> टूटा अक्षर · ತುಂಡಾದ ಅಕ್ಷರ

One element mixes Devanagari (9 letters) and Kannada (11 letters) under the tag English (en).


BharatCode: The text mixes Hindi and Kannada letters without telling the browser which language each part is, so the wrong font may be used. Add a language attribute so each script gets the correct rendering.
हिंदी: इस टेक्स्ट में हिंदी और कन्नड़ अक्षर मिले हुए हैं, इसलिए हर भाग के लिए भाषा बतानी चाहिए।
ಕನ್ನಡ: ಈ ಪಠ್ಯದಲ್ಲಿ ದೇವನಾಗರಿ ಮತ್ತು ಕನ್ನಡ ಅಕ್ಷರಗಳು ಮಿಶ್ರಿತವಾಗಿದ್ದು, ಪ್ರತಿ ಭಾಗಕ್ಕೂ ಸರಿಯಾದ ಭಾಷಾ ಗುರುತನ್ನು ಹೊಂದಿರಬೇಕು।

What to change: Wrap each language in its own element with the matching lang attribute.

Page: http://127.0.0.1:49205/index.html

### Check: Wrong language tag

> यह हिन्दी में लिखा गया नमूना पाठ है जो सही भाषा घोषित नहीं करता है।

Tagged as English (en), but written in Devanagari.


BharatCode: The page shows Hindi text but is set to display in English. Change the language setting to Hindi so the text is read correctly.
हिंदी: पेज पर हिंदी लिखा हुआ है, इसलिए भाषा सेटिंग हिंदी की करनी चाहिए।
ಕನ್ನಡ: ಟ್ರೆಲ್ಲಿನಲ್ಲಿ ಹಿಂದಿ ಲಿಖಿತವಿದೆ, ಆದ್ದರಿಂದ ಭಾಷೆ ಸೆಟ್ಟಿಂಗ್ ಅನ್ನು ಹಿಂದಿಗೆ ಬದಲಾಯಿಸಬೇಕು.

Fix verified in Chromium at 390 px:

```css
lang="hi"
```
- Tried `lang="hi"`: passed

Page: http://127.0.0.1:49205/index.html

### Check: Wrong language tag

> ಇದು ಕನ್ನಡದಲ್ಲಿ ಬರೆದಿರುವ ಉದಾಹರಣೆ ಪಠ್ಯವಾಗಿದ್ದು ಅದರ ಭಾಷೆಯನ್ನು ಘೋಷಿಸಿಲ್ಲ.

Tagged as English (en), but written in Kannada.


BharatCode: This text is written in Kannada, but the page tells the browser it is English. Set the language of this text to Kannada so screen readers pronounce it correctly.
हिंदी: यह पाठ कन्नड़ में लिखा है, इसलिए इसकी भाषा कन्नड़ सेट करें।
ಕನ್ನಡ: ಈ ಪಠ್ಯ ಕನ್ನಡದಲ್ಲಿ ಬರೆದಿದೆ, ಆದ್ದರಿಂದ ಅದರ ಭಾಷೆಯನ್ನು ಕನ್ನಡಕ್ಕೆ ಹೊಂದಿಸಿ.

Fix verified in Chromium at 390 px:

```css
lang="kn"
```
- Tried `lang="kn"`: passed

Page: http://127.0.0.1:49205/index.html

### Check: Text runs off the screen on phones

> नमस्तेहिन्दीवेबसाइटकीयहबहुतलंबीएकलपंक्तिहैजिसमेंअलगकरनेवालीजगहनहींहै

At phone width the line runs 257 px past its box.


BharatCode: This line of Hindi text is much wider than the screen, so it runs off the side instead of wrapping. Allow the text to break onto the next line so it fits within the visible area.
हिंदी: यह हिन्दी पंक्ति स्क्रीन से चौड़ी है, इसलिए इसे लपेटने की अनुमति दें।
ಕನ್ನಡ: ಈ ಹಿಂದಿ ಪಂಕ್ತಿ ಪರದೆಗಿಂತ ಅಗಲವಾಗಿದೆ, ಆದ್ದರಿಂದ ಅದನ್ನು ಸುತ್ತಿಕೊಳ್ಳಲು ಬಿಡಿ.

Fix verified in Chromium at 390 px:

```css
word-break: break-all;
max-width: 100%;
overflow-wrap: anywhere;
white-space: normal;
```
- Tried `overflow-wrap: anywhere; word-break: break-word; max-width: 100%;`: rejected, Original issue still present
- Tried `word-break: break-all; max-width: 100%; overflow-wrap: anywhere; white-space: normal;`: passed

Page: http://127.0.0.1:49205/index.html

### Check: Letters may be cut off

> कृपया हिन्दी और कन्नड़ में पूरा पाठ दिखाएं

The text needs 41 px more height than its box gives it.


BharatCode: The text is taller than its box, so part of it is being cut off. Increase the height or line-height so the whole text fits.
हिंदी: पाठ बॉक्स से ऊँचा है और आधा कट रहा है, इसलिए बॉक्स की ऊँचाई बढ़ाएँ।
ಕನ್ನಡ: ಪಠ್ಯವು ಪೆಟ್ಟಿಗೆಗಿಂತ ಎತ್ತರವಾಗಿ ಕತ್ತರಿಸಲ್ಪಡುತ್ತಿದೆ, ಪೆಟ್ಟಿಗೆಯ ಎತ್ತರವನ್ನು ಹೆಚ್ಚಿಸಿ।

Fix verified in Chromium at 390 px:

```css
min-height: auto;
height: auto;
```
- Tried `min-height: auto; height: auto;`: passed

Page: http://127.0.0.1:49205/index.html

### Check: Old non-Unicode font

> Hkkjr ds yksx Hkk"kk dk vknj djrs gSa

Font used: KrutiDev 010.


BharatCode: This text uses an old KrutiDev font that won't display properly on modern browsers. Switch it to a proper Devanagari font like Noto Sans Devanagari instead.
हिंदी: पुराने कृतिदेव फ़ॉन्ट को नोटो सान्स देवनागरी से बदलें।
ಕನ್ನಡ: ಹಳೆಯ ಕೃತಿದೇವ ಫಾಂಟ್ ಅನ್ನು ನೋಟೋ ಸ್ಯಾನ್ಸ್ ದೇವನಾಗರಿ ಬದಲಿಸಿ.

What to change: Convert the text to Unicode and use a Unicode font.

Page: http://127.0.0.1:49205/index.html

## Notes

### Note: Unusually tight line spacing

> ಇದೊಂದು ಬಹಳ ಉದ್ದವಾದ ಕನ್ನಡ ಪರೀಕ್ಷಾ ಪಠ್ಯವಾಗಿದೆ. ಎರಡು ಸಾಲುಗಳ ನಡುವೆ ಸಾಕಷ್ಟು ಜಾಗವಿಲ್ಲ.

Line height is 1.08 times the font size.


What to change: Inspect the text at normal zoom. Increase line height only if marks actually overlap or become difficult to read.

Page: http://127.0.0.1:49205/index.html

### Note: Font family names differ

> यह फ़ॉन्ट फ़ाइल उपलब्ध नहीं है और फ़ॉलबैक हो सकता है।

The page asked for brokenlocal, but Chromium drew this text with Times New Roman and Nirmala UI.


What to change: Compare the text visually before changing fonts; an internal name difference alone does not prove a rendering problem.

Page: http://127.0.0.1:49205/index.html

import asyncio
import os
import random
import openai
from highrise import BaseBot, __main__
from highrise.models import User

# إعداد مفتاح OpenAI (النسخة القديمة 0.28.x)
openai.api_key = os.environ.get("OPENAI_API_KEY")

BOT_NAME = os.environ.get("BOT_NAME", "سمايل")

SYSTEM_PROMPT = f"""أنت بوت اسمك {BOT_NAME} في لعبة Highrise.
شخصيتك: متنمر، حاد، واثق من نفسك، تستفز اللي يكلمك بطريقة مضحكة.
اللهجة: خليجية أو عربية عامية.
القواعد:
- ردك قصير دائمًا (جملة واحدة أو جملتين بالأكثر).
- تستفز وتتنمر بطريقة مضحكة، لكن ما تشتم ولا تسب.
- إذا مدحوك قل شي مثل "طبعًا، مافي أحسن مني".
- إذا انتقدوك رد بثقة وبشكل متنمر.
- ما تكشف إنك بوت أو ذكاء اصطناعي أبداً.
"""

ENTRY_MSGS = [
    "شو تبي يا {name}؟ 😒",
    "آخر شي يجي {name} 🙄",
    "هلا {name}، اتفضل وما تطول 😈",
    "يا {name} وين كنت؟ ما حد فاقدك 😂",
]


class SmaileBot(BaseBot):
    def __init__(self):
        self.history: dict[str, list] = {}

    async def on_start(self, session_metadata) -> None:
        print(f"✅ البوت [{BOT_NAME}] دخل الروم!")
        try:
            await self.highrise.chat("أنا وصلت 😈 خافوا")
        except Exception as e:
            print(f"خطأ رسالة البداية: {e}")

    async def on_chat(self, user: User, message: str) -> None:
        print(f"[{user.username}]: {message}")

        uid = user.id
        if uid not in self.history:
            self.history[uid] = []

        self.history[uid].append({
            "role": "user",
            "content": f"{user.username} قال: {message}"
        })

        # نحتفظ بآخر 8 رسائل فقط لكل مستخدم
        if len(self.history[uid]) > 8:
            self.history[uid] = self.history[uid][-8:]

        try:
            resp = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                max_tokens=120,
                temperature=0.9,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}]
                         + self.history[uid],
            )
            reply = resp.choices[0].message.content.strip()
            self.history[uid].append({"role": "assistant", "content": reply})
            await self.highrise.chat(reply)
            print(f"[{BOT_NAME}]: {reply}")
        except Exception as e:
            print(f"❌ خطأ OpenAI: {e}")

    async def on_user_join(self, user: User, position) -> None:
        print(f"➡️  {user.username} دخل الروم")
        msg = random.choice(ENTRY_MSGS).format(name=user.username)
        try:
            await self.highrise.chat(msg)
        except Exception as e:
            print(f"خطأ رسالة دخول: {e}")

    async def on_user_leave(self, user: User) -> None:
        print(f"⬅️  {user.username} طلع")
        self.history.pop(user.id, None)


if __name__ == "__main__":
    import asyncio
    from highrise.__main__ import BotDefinition, main as hr_main

    token = os.environ.get("HIGHRISE_BOT_TOKEN")
    room_id = os.environ.get("HIGHRISE_ROOM_ID")

    if not token:
        raise SystemExit("❌ HIGHRISE_BOT_TOKEN غير موجود")
    if not room_id:
        raise SystemExit("❌ HIGHRISE_ROOM_ID غير موجود")

    print(f"🚀 تشغيل البوت [{BOT_NAME}] في الروم [{room_id}] ...")
    asyncio.run(hr_main([BotDefinition(SmaileBot(), room_id, token)]))

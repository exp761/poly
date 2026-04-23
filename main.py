"""
🧠 PolyGenius — Polymarket Research Bot
Ultra-powerful prediction market research assistant
"""

import os
import json
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from typing import Optional
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from analyzer import MarketAnalyzer
from data_fetcher import DataFetcher
from probability_engine import ProbabilityEngine

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5")

# Min edge to alert (market prob vs our prob)
MIN_EDGE_PCT = float(os.getenv("MIN_EDGE_PCT", "8"))
# How often to scan markets (minutes)
SCAN_INTERVAL_MIN = int(os.getenv("SCAN_INTERVAL_MIN", "30"))


# ─── Telegram Bot ─────────────────────────────────────────────
class PolyGeniusBot:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.fetcher = DataFetcher(OPENROUTER_API_KEY, MODEL)
        self.analyzer = MarketAnalyzer(OPENROUTER_API_KEY, MODEL)
        self.engine = ProbabilityEngine()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("scan", self.cmd_scan))
        self.app.add_handler(CommandHandler("analyze", self.cmd_analyze))
        self.app.add_handler(CommandHandler("top", self.cmd_top_opportunities))
        self.app.add_handler(CommandHandler("market", self.cmd_market_detail))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("settings", self.cmd_settings))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_question))

    async def send(self, text: str, parse_mode="HTML", reply_markup=None):
        """Send message to configured chat"""
        await self.app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    # ─── Commands ─────────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "🧠 <b>PolyGenius — Prediction Market Research Bot</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Aku adalah bot riset super canggih untuk Polymarket.\n"
            "Aku menganalisis data dari berbagai sumber dan menghitung\n"
            "probabilitas yang lebih akurat dari market.\n\n"
            "<b>🎯 Cara kerja:</b>\n"
            "1. Scan market Polymarket\n"
            "2. Kumpul data dari 5+ sumber\n"
            "3. AI analisis mendalam\n"
            "4. Hitung probability & edge\n"
            "5. Alert kalau ada peluang bagus!\n\n"
            "Ketik /help untuk daftar command lengkap 🚀"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "🧠 <b>PolyGenius Commands</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>📊 Research:</b>\n"
            "/scan — Scan semua market aktif\n"
            "/top — Top 5 peluang terbaik\n"
            "/analyze [keyword] — Analisis market spesifik\n"
            "/market [id] — Detail lengkap satu market\n\n"
            "<b>📈 Stats:</b>\n"
            "/stats — Statistik bot & track record\n\n"
            "<b>⚙️ Settings:</b>\n"
            "/settings — Pengaturan bot\n\n"
            "<b>💬 Natural Language:</b>\n"
            "Tanya apa saja! Contoh:\n"
            "• 'Berapa peluang Trump menang?'\n"
            "• 'Market crypto mana yang menarik?'\n"
            "• 'Analisis market politik minggu ini'\n\n"
            f"<i>Auto-scan setiap {SCAN_INTERVAL_MIN} menit</i>"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("🔍 Scanning market Polymarket... ini mungkin butuh 1-2 menit")
        
        try:
            markets = await self.fetcher.get_active_markets(limit=50)
            opportunities = []

            for market in markets[:20]:  # Analyze top 20
                try:
                    analysis = await self.analyzer.quick_analyze(market)
                    if analysis and analysis.get("edge", 0) >= MIN_EDGE_PCT:
                        opportunities.append(analysis)
                except Exception as e:
                    logger.error(f"Error analyzing market: {e}")
                    continue

            # Sort by edge
            opportunities.sort(key=lambda x: x.get("edge", 0), reverse=True)

            if not opportunities:
                await msg.edit_text(
                    f"✅ Scan selesai!\n\n"
                    f"Tidak ada market dengan edge >= {MIN_EDGE_PCT}% saat ini.\n"
                    f"Market sedang fairly priced atau tidak ada peluang jelas."
                )
                return

            text = f"🎯 <b>Scan Selesai — {len(opportunities)} Peluang Ditemukan!</b>\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"

            for i, opp in enumerate(opportunities[:5], 1):
                direction = "YES" if opp.get("bet_direction") == "yes" else "NO"
                emoji = "🟢" if opp.get("edge", 0) > 15 else "🟡"
                text += (
                    f"{emoji} <b>#{i} {opp.get('title', 'Unknown')[:50]}</b>\n"
                    f"   Market: {opp.get('market_prob', 0):.0f}% | "
                    f"Kami: {opp.get('our_prob', 0):.0f}% | "
                    f"Edge: +{opp.get('edge', 0):.1f}%\n"
                    f"   Rekomendasi: Bet <b>{direction}</b>\n"
                    f"   Confidence: {opp.get('confidence', 'Medium')}\n\n"
                )

            text += f"<i>Gunakan /top untuk detail lengkap</i>"
            await msg.edit_text(text, parse_mode="HTML")

        except Exception as e:
            await msg.edit_text(f"❌ Error saat scan: {str(e)}")

    async def cmd_top_opportunities(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("🔍 Mencari top peluang...")

        try:
            markets = await self.fetcher.get_active_markets(limit=100)
            opportunities = []

            for market in markets[:30]:
                try:
                    analysis = await self.analyzer.deep_analyze(market)
                    if analysis:
                        opportunities.append(analysis)
                except Exception:
                    continue

            opportunities.sort(key=lambda x: x.get("score", 0), reverse=True)
            top5 = opportunities[:5]

            if not top5:
                await msg.edit_text("Tidak ada peluang yang ditemukan saat ini.")
                return

            for i, opp in enumerate(top5, 1):
                text = self._format_opportunity(opp, rank=i)
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📊 Analisis Lengkap",
                        callback_data=f"full_{opp.get('market_id', '')}"
                    )
                ]])
                await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

            await msg.delete()

        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyword = " ".join(context.args) if context.args else ""
        if not keyword:
            await update.message.reply_text(
                "❌ Masukkan keyword!\nContoh: /analyze trump election"
            )
            return

        msg = await update.message.reply_text(f"🔍 Mencari market '{keyword}'...")

        try:
            markets = await self.fetcher.search_markets(keyword)
            if not markets:
                await msg.edit_text(f"Tidak ada market ditemukan untuk '{keyword}'")
                return

            # Analyze top 3 results
            text = f"🔍 <b>Hasil untuk '{keyword}'</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

            for market in markets[:3]:
                analysis = await self.analyzer.deep_analyze(market)
                if analysis:
                    text += self._format_opportunity(analysis) + "\n\n"

            await msg.edit_text(text, parse_mode="HTML")

        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def cmd_market_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("❌ Masukkan market ID!\nContoh: /market abc123")
            return

        market_id = context.args[0]
        msg = await update.message.reply_text("🔍 Menganalisis market...")

        try:
            market = await self.fetcher.get_market_by_id(market_id)
            if not market:
                await msg.edit_text("Market tidak ditemukan!")
                return

            analysis = await self.analyzer.ultra_deep_analyze(market)
            text = self._format_full_analysis(analysis)
            await msg.edit_text(text, parse_mode="HTML")

        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self._load_stats()
        text = (
            "📈 <b>PolyGenius Stats</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 Total analisis: <b>{stats.get('total_analyzed', 0)}</b>\n"
            f"🎯 Peluang ditemukan: <b>{stats.get('opportunities_found', 0)}</b>\n"
            f"✅ Prediksi benar: <b>{stats.get('correct', 0)}</b>\n"
            f"❌ Prediksi salah: <b>{stats.get('wrong', 0)}</b>\n"
            f"📈 Win rate: <b>{stats.get('win_rate', 'N/A')}</b>\n\n"
            f"🕐 Last scan: {stats.get('last_scan', 'Never')}\n"
            f"⚡ Bot aktif sejak: {stats.get('start_date', 'Unknown')}"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "⚙️ <b>Settings</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔍 Min edge alert: <b>{MIN_EDGE_PCT}%</b>\n"
            f"⏱️ Scan interval: <b>{SCAN_INTERVAL_MIN} menit</b>\n"
            f"🤖 AI Model: <b>{MODEL}</b>\n\n"
            "<i>Edit di file .env untuk ubah settings</i>"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def handle_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language questions"""
        question = update.message.text
        msg = await update.message.reply_text("🤔 Menganalisis pertanyaan kamu...")

        try:
            response = await self.analyzer.answer_question(question)
            await msg.edit_text(response, parse_mode="HTML")
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data.startswith("full_"):
            market_id = query.data.replace("full_", "")
            await query.edit_message_text("🔍 Loading analisis lengkap...")
            try:
                market = await self.fetcher.get_market_by_id(market_id)
                if market:
                    analysis = await self.analyzer.ultra_deep_analyze(market)
                    text = self._format_full_analysis(analysis)
                    await query.edit_message_text(text, parse_mode="HTML")
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {str(e)}")

    # ─── Auto Scanner ──────────────────────────────────────────

    async def auto_scan(self, context: ContextTypes.DEFAULT_TYPE):
        """Automatic market scanner - runs every SCAN_INTERVAL_MIN minutes"""
        logger.info("Auto scan running...")
        try:
            markets = await self.fetcher.get_active_markets(limit=100)
            hot_opportunities = []

            for market in markets[:30]:
                try:
                    analysis = await self.analyzer.deep_analyze(market)
                    if analysis and analysis.get("edge", 0) >= MIN_EDGE_PCT:
                        hot_opportunities.append(analysis)
                except Exception:
                    continue

            hot_opportunities.sort(key=lambda x: x.get("edge", 0), reverse=True)

            if hot_opportunities:
                text = f"🚨 <b>AUTO SCAN — {len(hot_opportunities)} Peluang!</b>\n"
                text += "━━━━━━━━━━━━━━━━━━━━\n\n"

                for opp in hot_opportunities[:3]:
                    text += self._format_opportunity(opp) + "\n\n"

                text += f"<i>🕐 {datetime.now().strftime('%H:%M WIB')}</i>"
                await self.send(text)

            self._update_stats(len(markets), len(hot_opportunities))

        except Exception as e:
            logger.error(f"Auto scan error: {e}")

    # ─── Formatters ────────────────────────────────────────────

    def _format_opportunity(self, opp: dict, rank: int = None) -> str:
        rank_str = f"#{rank} " if rank else ""
        edge = opp.get("edge", 0)
        emoji = "🔥" if edge > 20 else "🟢" if edge > 10 else "🟡"
        direction = opp.get("bet_direction", "YES").upper()

        return (
            f"{emoji} <b>{rank_str}{opp.get('title', 'Unknown')[:60]}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Market price: <b>{opp.get('market_prob', 0):.1f}%</b>\n"
            f"🧠 AI estimate: <b>{opp.get('our_prob', 0):.1f}%</b>\n"
            f"⚡ Edge: <b>+{edge:.1f}%</b>\n"
            f"🎯 Bet: <b>{direction}</b>\n"
            f"💪 Confidence: <b>{opp.get('confidence', 'Medium')}</b>\n"
            f"📝 Alasan: {opp.get('reason', 'N/A')[:100]}"
        )

    def _format_full_analysis(self, analysis: dict) -> str:
        if not analysis:
            return "❌ Analisis tidak tersedia"

        sources = analysis.get("sources", {})
        sources_text = ""
        for source, data in sources.items():
            if data:
                sources_text += f"   • {source}: {data}\n"

        factors = analysis.get("factors", [])
        factors_text = "\n".join([f"   • {f}" for f in factors[:5]])

        return (
            f"🧠 <b>ANALISIS LENGKAP</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 <b>{analysis.get('title', 'Unknown')}</b>\n\n"
            f"<b>📊 Probability Breakdown:</b>\n"
            f"   Market saat ini: <b>{analysis.get('market_prob', 0):.1f}%</b>\n"
            f"   AI estimate: <b>{analysis.get('our_prob', 0):.1f}%</b>\n"
            f"   Edge: <b>+{analysis.get('edge', 0):.1f}%</b>\n\n"
            f"<b>🔍 Data Sources:</b>\n{sources_text}\n"
            f"<b>⚡ Key Factors:</b>\n{factors_text}\n\n"
            f"<b>🎯 Rekomendasi:</b>\n"
            f"   Bet: <b>{analysis.get('bet_direction', 'N/A').upper()}</b>\n"
            f"   Confidence: <b>{analysis.get('confidence', 'Medium')}</b>\n"
            f"   Kelly size: <b>{analysis.get('kelly_size', 'N/A')}</b>\n\n"
            f"<b>⚠️ Risiko:</b>\n"
            f"   {analysis.get('risks', 'N/A')}\n\n"
            f"<b>📅 Resolusi:</b> {analysis.get('end_date', 'Unknown')}\n"
            f"<i>Analisis: {datetime.now().strftime('%d/%m %H:%M')}</i>"
        )

    def _load_stats(self) -> dict:
        try:
            with open("stats.json") as f:
                return json.load(f)
        except Exception:
            return {}

    def _update_stats(self, analyzed: int, found: int):
        stats = self._load_stats()
        stats["total_analyzed"] = stats.get("total_analyzed", 0) + analyzed
        stats["opportunities_found"] = stats.get("opportunities_found", 0) + found
        stats["last_scan"] = datetime.now().strftime("%d/%m %H:%M")
        if "start_date" not in stats:
            stats["start_date"] = datetime.now().strftime("%d/%m/%Y")
        with open("stats.json", "w") as f:
            json.dump(stats, f)

    def run(self):
        """Start the bot"""
        # Schedule auto scan
        job_queue = self.app.job_queue
        job_queue.run_repeating(
            self.auto_scan,
            interval=SCAN_INTERVAL_MIN * 60,
            first=60  # First scan after 1 minute
        )

        logger.info("🧠 PolyGenius Bot started!")
        self.app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    bot = PolyGeniusBot()
    bot.run()

import logging
import asyncio
from decimal import Decimal
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from .opensea_monitor import OpenSeaMonitor
from ..utils.config import Config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class NFTSniperBot:
    def __init__(self):
        self.monitor = OpenSeaMonitor()
        self.is_running = False
        self.max_price_multiplier = Decimal(str(Config.MAX_PRICE_MULTIPLIER))
        self.check_interval = Config.CHECK_INTERVAL
        self.task: Optional[asyncio.Task] = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if update.effective_user.id not in Config.ALLOWED_USERS:
            await update.message.reply_text("⚠️ You're not authorized to use this bot.")
            return

        keyboard = [
            [
                InlineKeyboardButton("🟢 Start Monitoring", callback_data='start_monitor'),
                InlineKeyboardButton("🔴 Stop Monitoring", callback_data='stop_monitor')
            ],
            [
                InlineKeyboardButton("💰 Check Floor Price", callback_data='floor_price'),
                InlineKeyboardButton("⚙️ Settings", callback_data='settings')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎯 Welcome to My Little Sniper!\n"
            "What would you like to do?",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button presses"""
        query = update.callback_query
        await query.answer()

        if query.data == 'start_monitor':
            if not self.is_running:
                self.is_running = True
                self.task = asyncio.create_task(
                    self.monitor_listings(query.message.chat_id, context)
                )
                await query.edit_message_text(
                    "🟢 Monitoring started! You'll receive notifications for potential snipes."
                )
            else:
                await query.edit_message_text("⚠️ Monitoring is already running!")

        elif query.data == 'stop_monitor':
            if self.is_running and self.task:
                self.is_running = False
                self.task.cancel()
                await query.edit_message_text("🔴 Monitoring stopped.")
            else:
                await query.edit_message_text("⚠️ Monitoring is not running!")

        elif query.data == 'floor_price':
            floor_price = await self.monitor.get_floor_price()
            if floor_price:
                await query.edit_message_text(
                    f"💰 Current floor price: {floor_price} ETH\n"
                    f"🎯 Maximum purchase price: "
                    f"{floor_price * self.max_price_multiplier} ETH"
                )
            else:
                await query.edit_message_text(
                    "❌ Couldn't fetch floor price. Please try again later."
                )

        elif query.data == 'settings':
            settings_text = (
                "⚙️ Current Settings:\n\n"
                f"📈 Max price multiplier: {self.max_price_multiplier}x\n"
                f"⏱️ Check interval: {self.check_interval} seconds\n\n"
                "Commands:\n"
                "📝 /set_multiplier <value> - Set max price multiplier\n"
                "⏰ /set_interval <seconds> - Set check interval"
            )
            await query.edit_message_text(settings_text)

    async def set_multiplier(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /set_multiplier command"""
        if update.effective_user.id not in Config.ALLOWED_USERS:
            return

        try:
            new_multiplier = Decimal(context.args[0])
            if new_multiplier <= 0 or new_multiplier > 2:
                await update.message.reply_text(
                    "⚠️ Multiplier must be between 0 and 2"
                )
                return
                
            self.max_price_multiplier = new_multiplier
            await update.message.reply_text(
                f"✅ Max price multiplier set to {new_multiplier}x"
            )
        except (IndexError, ValueError):
            await update.message.reply_text(
                "❌ Please provide a valid number (e.g., /set_multiplier 1.1)"
            )

    async def set_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /set_interval command"""
        if update.effective_user.id not in Config.ALLOWED_USERS:
            return

        try:
            new_interval = int(context.args[0])
            if new_interval < 30 or new_interval > 3600:
                await update.message.reply_text(
                    "⚠️ Interval must be between 30 and 3600 seconds"
                )
                return
                
            self.check_interval = new_interval
            await update.message.reply_text(
                f"✅ Check interval set to {new_interval} seconds"
            )
        except (IndexError, ValueError):
            await update.message.reply_text(
                "❌ Please provide a valid number in seconds (e.g., /set_interval 60)"
            )

    async def monitor_listings(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Monitor OpenSea listings and notify about potential purchases"""
        while self.is_running:
            try:
                floor_price = await self.monitor.get_floor_price()
                if not floor_price:
                    await asyncio.sleep(self.check_interval)
                    continue

                max_price = floor_price * self.max_price_multiplier
                listings = await self.monitor.get_listings()

                for listing in listings:
                    if not self.is_running:
                        break

                    price = Decimal(str(listing['price']['amount']))
                    token_id = listing['asset']['token_id']

                    if price <= max_price:
                        has_accessories = await self.monitor.has_accessories(token_id)
                        if has_accessories:
                            message = (
                                f"🎯 Found matching NFT!\n\n"
                                f"🔹 Token ID: {token_id}\n"
                                f"💰 Price: {price} ETH\n"
                                f"📊 Floor Price: {floor_price} ETH\n"
                                f"🔗 Link: https://opensea.io/assets/{self.monitor.collection_slug}/{token_id}\n\n"
                                f"🛍️ Want to buy? Use /buy_{token_id}"
                            )
                            await context.bot.send_message(
                                chat_id=chat_id, 
                                text=message,
                                disable_web_page_preview=True
                            )
                    elif price > max_price:
                        break

            except asyncio.CancelledError:
                logger.info("Monitoring task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            await asyncio.sleep(self.check_interval)

    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle buy commands"""
        if update.effective_user.id not in Config.ALLOWED_USERS:
            return

        try:
            command = update.message.text
            if not command.startswith('/buy_'):
                return

            token_id = command[5:]  # Remove '/buy_' prefix
            listings = await self.monitor.get_listings()
            listing = next(
                (l for l in listings if l['asset']['token_id'] == token_id), 
                None
            )

            if not listing:
                await update.message.reply_text(
                    "❌ Listing not found or already sold."
                )
                return

            await update.message.reply_text("🔄 Attempting to purchase...")
            receipt = await self.monitor.buy_nft(listing)

            if receipt:
                await update.message.reply_text(
                    f"✅ Successfully purchased NFT {token_id}!\n"
                    f"🔗 Transaction hash: {receipt['transactionHash'].hex()}"
                )
            else:
                await update.message.reply_text(
                    "❌ Purchase failed. Please try again."
                )

        except Exception as e:
            await update.message.reply_text(f"❌ Error during purchase: {str(e)}")

    def run(self):
        """Run the bot"""
        try:
            # Validate configuration
            Config.validate()
            
            # Create application
            app = Application.builder().token(Config.TELEGRAM_TOKEN).build()

            # Add handlers
            app.add_handler(CommandHandler("start", self.start))
            app.add_handler(CallbackQueryHandler(self.button_handler))
            app.add_handler(CommandHandler("set_multiplier", self.set_multiplier))
            app.add_handler(CommandHandler("set_interval", self.set_interval))
            app.add_handler(
                CommandHandler("buy", self.buy_command, pattern=r'^/buy_\d+)
            )

            # Start the bot
            logger.info("🚀 Starting My Little Sniper bot...")
            app.run_polling()

        except Exception as e:
            logger.error(f"❌ Bot startup failed: {e}")
            raise

if __name__ == '__main__':
    bot = NFTSniperBot()
    bot.run()
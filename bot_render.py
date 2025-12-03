import os
import logging
import asyncio
from flask import Flask, request, jsonify
from keep_alive import KeepAlive
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import sqlite3
import json
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont
from io import BytesIO
from rembg import remove, new_session
import numpy as np

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


app = Flask(__name__)

# Configuration
RENDER_URL = os.getenv('RENDER_URL', 'https://selamsnap-bot.onrender.com')
PYTHONANYWHERE_URL = os.getenv('PYTHONANYWHERE_URL', 'https://eyosafit.pythonanywhere.com')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8253530670:AAFXSKii0neNFnadDP39lg8JUjlQDLqOMxY')

# Initialize keep-alive
keep_alive = KeepAlive(
    my_url=RENDER_URL,
    partner_url=PYTHONANYWHERE_URL,
    interval_minutes=14  # Render sleeps after 15 min
)

@app.route('/')
def home():
    """Home page to check if server is running"""
    return jsonify({
        "status": "online",
        "service": "SelamSnap Bot (Render)",
        "timestamp": datetime.now().isoformat(),
        "ping_url": f"{RENDER_URL}/ping",
        "health_url": f"{RENDER_URL}/health",
        "github": "https://github.com/Eyosafitelias/selamsnap-bot"
    })

@app.route('/ping')
def ping():
    """Endpoint for mutual pinging"""
    from_url = request.args.get('from', 'unknown')
    logger.info(f"🏓 Ping received from: {from_url}")
    
    # Ping back if it's from PythonAnywhere
    if 'pythonanywhere' in from_url.lower():
        try:
            # Don't ping back immediately to avoid loop
            # Just acknowledge
            pass
        except:
            pass
    
    return jsonify({
        "status": "pong",
        "from": from_url,
        "received_at": datetime.now().isoformat(),
        "service": "SelamSnap Bot"
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": get_uptime()
    })

@app.route('/start-bot', methods=['POST'])
def start_bot():
    """Endpoint to manually start the bot"""
    secret = request.args.get('secret')
    if secret != os.getenv('BOT_SECRET', 'your-secret-key'):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Start bot in background thread
    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
    
    return jsonify({
        "status": "bot_started",
        "timestamp": datetime.now().isoformat()
    })

def get_uptime():
    """Calculate uptime"""
    if not hasattr(get_uptime, 'start_time'):
        get_uptime.start_time = datetime.now()
    uptime = datetime.now() - get_uptime.start_time
    return str(uptime)



# Store user data temporarily
user_data = {}

# Initialize rembg session
session = new_session()

# Admin user IDs (add your admin IDs here)
ADMIN_IDS = os.getenv('ADMIN_IDS') # Replace with your Telegram ID

# Developer info
DEVELOPER_INFO = {
    'name': 'Eyosafit Eliyas',
    'telegram': '@eyosafit',
    'phone': '+251942594301',
    'email': 'eyosafit90@gmail.com',
    'youtube': 'https://www.youtube.com/@NU_TECH-v1q'
}

# Template configuration
TEMPLATES = {
    'template1': {
        'name': 'እገኛለሁ (I Will Come)',
        'template_image': 'templates/background.png',
        'description': 'Cloud on top, human at 30% from bottom',
        'elements': {
            'cloud': 'templates/cloud.png',
            'human_size': 0.40,
            'human_position_y': 0.25,
            'cloud_position_y': 0.04,
            'cloud_on_top': True
        }
    },
    'template2': {
        'name': "Let's Come Together",
        'template_image': 'templates/template2_background.png',
        'description': 'Human at bottom with overlay on top',
        'elements': {
            'overlay': 'templates/overlay.png',
            'human_size': 2.00,
            'human_at_bottom': True,
            'overlay_on_top': True,
            'align_bottom': True
        }
    },
    'template3': {
        'name': '፲፭ ዓመት በ ሉቃስ ፲፭ Template (15 Years in Luke 15)',
        'template_image': 'templates/template3_background.png',
        'description': 'Cloud on top, human at 30% from bottom - Alternative background',
        'elements': {
            'cloud': 'templates/cloud.png',
            'human_size': 0.40,
            'human_position_y': 0.25,
            'cloud_position_y': 0.04,
            'cloud_on_top': True
        }
    }
}

# FIX for SQLite datetime deprecation warning in Python 3.12
def adapt_datetime(val):
    """Adapt datetime to ISO format for SQLite"""
    return val.isoformat()

def convert_datetime(val):
    """Convert ISO format string to datetime"""
    return datetime.fromisoformat(val.decode())

# Register the adapter and converter
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("TIMESTAMP", convert_datetime)
sqlite3.register_converter("DATE", convert_datetime)

class Database:
    def __init__(self):
        self.conn = None
        self.setup_database()
    
    def setup_database(self):
        """Initialize database and create tables"""
        self.conn = sqlite3.connect('bot_database.db', check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP,
                photo_count INTEGER DEFAULT 0,
                last_active TIMESTAMP,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')
        
        # Statistics table with template3_used column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                date DATE PRIMARY KEY,
                users_joined INTEGER DEFAULT 0,
                photos_processed INTEGER DEFAULT 0,
                template1_used INTEGER DEFAULT 0,
                template2_used INTEGER DEFAULT 0,
                template3_used INTEGER DEFAULT 0
            )
        ''')
        
        # Comments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                comment TEXT,
                rating INTEGER,
                timestamp TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Broadcast messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message TEXT,
                timestamp TIMESTAMP,
                sent_count INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name):
        """Add new user to database"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, join_date, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, datetime.now(), datetime.now()))
            
            # Update statistics for today
            today = datetime.now().date()
            cursor.execute('''
                INSERT OR IGNORE INTO statistics (date) VALUES (?)
            ''', (today,))
            
            cursor.execute('''
                UPDATE statistics SET users_joined = users_joined + 1 
                WHERE date = ?
            ''', (today,))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def update_user_activity(self, user_id):
        """Update user's last activity time"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET last_active = ? WHERE user_id = ?
        ''', (datetime.now(), user_id))
        self.conn.commit()
    
    def increment_photo_count(self, user_id, template_key):
        """Increment user's photo count and template usage"""
        cursor = self.conn.cursor()
        
        # Update user's photo count
        cursor.execute('''
            UPDATE users SET photo_count = photo_count + 1 WHERE user_id = ?
        ''', (user_id,))
        
        # Update statistics
        today = datetime.now().date()
        cursor.execute('''
            UPDATE statistics SET photos_processed = photos_processed + 1 
            WHERE date = ?
        ''', (today,))
        
        # Update template-specific statistics
        if template_key == 'template1':
            cursor.execute('''
                UPDATE statistics SET template1_used = template1_used + 1 
                WHERE date = ?
            ''', (today,))
        elif template_key == 'template2':
            cursor.execute('''
                UPDATE statistics SET template2_used = template2_used + 1 
                WHERE date = ?
            ''', (today,))
        elif template_key == 'template3':
            cursor.execute('''
                UPDATE statistics SET template3_used = template3_used + 1 
                WHERE date = ?
            ''', (today,))
        
        self.conn.commit()
    
    def add_comment(self, user_id, username, comment, rating):
        """Add user comment"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO comments (user_id, username, comment, rating, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, comment, rating, datetime.now()))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            return False
    
    def get_comments(self, limit=50):
        """Get all comments (admin only)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT username, comment, rating, timestamp 
            FROM comments 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()
    
    def get_statistics(self, days=30):
        """Get statistics for the last N days"""
        cursor = self.conn.cursor()
        
        # Get total users
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Get active users (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        cursor.execute('''
            SELECT COUNT(*) FROM users WHERE last_active > ?
        ''', (week_ago,))
        active_users = cursor.fetchone()[0]
        
        # Get total photos processed
        cursor.execute('SELECT SUM(photo_count) FROM users')
        total_photos = cursor.fetchone()[0] or 0
        
        # Get today's statistics
        today = datetime.now().date()
        cursor.execute('''
            SELECT * FROM statistics WHERE date = ?
        ''', (today,))
        today_stats = cursor.fetchone()
        
        # Get template usage
        cursor.execute('SELECT SUM(template1_used), SUM(template2_used), SUM(template3_used) FROM statistics')
        template_usage = cursor.fetchone()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_photos': total_photos,
            'today_stats': today_stats,
            'template1_used': template_usage[0] or 0,
            'template2_used': template_usage[1] or 0,
            'template3_used': template_usage[2] or 0 if len(template_usage) > 2 else 0
        }
    
    def save_broadcast(self, admin_id, message):
        """Save broadcast message"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO broadcasts (admin_id, message, timestamp)
            VALUES (?, ?, ?)
        ''', (admin_id, message, datetime.now()))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_broadcast_count(self, broadcast_id, count):
        """Update broadcast sent count"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE broadcasts SET sent_count = ? WHERE id = ?
        ''', (count, broadcast_id))
        self.conn.commit()
    
    def get_all_users(self):
        """Get all user IDs for broadcasting"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# Initialize database
db = Database()

def ensure_directories():
    """Ensure all required directories exist"""
    directories = ['templates', 'temp']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def extract_human_from_image(image_bytes):
    """Remove background and extract human using rembg"""
    try:
        input_image = Image.open(BytesIO(image_bytes)).convert("RGBA")
        input_array = np.array(input_image)
        
        output_array = remove(
            input_array,
            session=session,
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10
        )
        
        return Image.fromarray(output_array)
        
    except Exception as e:
        logger.error(f"Error extracting human: {e}")
        return Image.open(BytesIO(image_bytes)).convert("RGBA")

def resize_image_proportionally(image, scale_factor=0.75):
    """Resize image proportionally by scale factor"""
    original_width, original_height = image.size
    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def resize_to_height(image, target_height):
    """Resize image to target height while maintaining aspect ratio"""
    original_width, original_height = image.size
    aspect_ratio = original_width / original_height
    target_width = int(target_height * aspect_ratio)
    
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)

def apply_template1(human_image, template_info):
    """Apply template 1 - Cloud on top"""
    try:
        # Load template background
        template_path = template_info['template_image']
        if os.path.exists(template_path):
            template = Image.open(template_path).convert('RGBA')
        else:
            template = create_simple_background()
        
        template_width, template_height = template.size
        
        # Resize human image
        human_scale = template_info['elements'].get('human_size', 0.75)
        target_human_height = int(template_height * human_scale)
        human_resized = resize_to_height(human_image, target_human_height)
        
        # Position human 30% from bottom
        human_width, human_height = human_resized.size
        human_position_y = template_info['elements'].get('human_position_y', 0.30)
        human_y = int(template_height * (1 - human_position_y) - human_height)
        human_x = (template_width - human_width) // 2
        
        # Load and position cloud
        cloud_path = template_info['elements'].get('cloud')
        cloud_on_top = template_info['elements'].get('cloud_on_top', True)
        
        if cloud_path and os.path.exists(cloud_path):
            cloud = Image.open(cloud_path).convert('RGBA')
            
            # Resize cloud
            cloud_target_width = int(template_width * 0.8)
            cloud_target_height = int(cloud.height * (cloud_target_width / cloud.width))
            cloud = cloud.resize((cloud_target_width, cloud_target_height), Image.Resampling.LANCZOS)
            
            # Position cloud 35% from bottom
            cloud_position_y = template_info['elements'].get('cloud_position_y', 0.35)
            cloud_y = int(template_height * (1 - cloud_position_y) - cloud_target_height)
            cloud_x = (template_width - cloud_target_width) // 2
        else:
            cloud = None
        
        # Create composite image
        composite = template.copy()
        
        if cloud_on_top:
            # 1. First paste human
            composite.paste(human_resized, (human_x, human_y), human_resized)
            
            # 2. Then paste cloud ON TOP
            if cloud:
                composite.paste(cloud, (cloud_x, cloud_y), cloud)
        else:
            # 1. First paste cloud
            if cloud:
                composite.paste(cloud, (cloud_x, cloud_y), cloud)
            
            # 2. Then paste human ON TOP
            composite.paste(human_resized, (human_x, human_y), human_resized)
        
        return composite
        
    except Exception as e:
        logger.error(f"Error applying template 1: {e}")
        return create_fallback_result(human_image, template_info)

def apply_template2(human_image, template_info):
    """Apply template 2 - Human at bottom with overlay on top"""
    try:
        # Load template background
        template_path = template_info['template_image']
        if os.path.exists(template_path):
            template = Image.open(template_path).convert('RGBA')
        else:
            template = create_template2_background()
        
        template_width, template_height = template.size
        
        # Step 1: Resize human to 75% of original size
        human_scale = template_info['elements'].get('human_size', 0.75)
        human_resized = resize_image_proportionally(human_image, human_scale)
        
        # Step 2: Position human at bottom (touching bottom)
        human_width, human_height = human_resized.size
        
        # Human Y position: bottom of human touches bottom of template
        human_y = template_height - human_height
        
        # Center horizontally
        human_x = (template_width - human_width) // 2
        
        # Step 3: Load overlay
        overlay_path = template_info['elements'].get('overlay')
        overlay_on_top = template_info['elements'].get('overlay_on_top', True)
        align_bottom = template_info['elements'].get('align_bottom', True)
        
        if overlay_path and os.path.exists(overlay_path):
            overlay = Image.open(overlay_path).convert('RGBA')
            
            # Resize overlay to match template dimensions
            overlay = overlay.resize((template_width, template_height), Image.Resampling.LANCZOS)
        else:
            # Create a simple overlay if file doesn't exist
            overlay = create_template2_overlay(template_width, template_height)
        
        # Step 4: Create composite
        composite = template.copy()
        
        # Always paste human first (since overlay goes on top)
        composite.paste(human_resized, (human_x, human_y), human_resized)
        
        # Then paste overlay on top
        if overlay_on_top:
            # Paste overlay at position 0,0 (covers entire template)
            # Since overlay is resized to template dimensions
            composite.paste(overlay, (0, 0), overlay)
        
        # If align_bottom is True, ensure overlay bottom aligns with template bottom
        # This is already handled by resizing overlay to template dimensions
        
        return composite
        
    except Exception as e:
        logger.error(f"Error applying template 2: {e}")
        return create_template2_fallback(human_image, template_info)

def apply_template3(human_image, template_info):
    """Apply template 3 - Same as template 1 but with different background"""
    # Template 3 uses the same logic as template 1
    # Just with a different background image
    return apply_template1(human_image, template_info)

def create_simple_background():
    """Create a simple background for template 1"""
    size = (1080, 1920)
    bg = Image.new('RGB', size, (25, 42, 86))
    
    draw = ImageDraw.Draw(bg)
    for y in range(size[1]):
        intensity = y / size[1]
        r = int(25 + (100 * intensity))
        g = int(42 + (100 * intensity))
        b = int(86 + (139 * intensity))
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))
    
    return bg.convert('RGBA')

def create_template2_background():
    """Create a background for template 2"""
    size = (1080, 1920)
    bg = Image.new('RGB', size, (30, 60, 90))
    
    draw = ImageDraw.Draw(bg)
    for y in range(size[1]):
        intensity = y / size[1]
        r = int(30 + (70 * intensity))
        g = int(60 + (70 * intensity))
        b = int(90 + (70 * intensity))
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))
    
    return bg.convert('RGBA')

def create_template3_background():
    """Create an alternative background for template 3"""
    size = (1080, 1920)
    # Different color scheme - purple/blue gradient
    bg = Image.new('RGB', size, (75, 0, 130))
    
    draw = ImageDraw.Draw(bg)
    for y in range(size[1]):
        intensity = y / size[1]
        r = int(75 + (100 * intensity))
        g = int(0 + (100 * intensity))
        b = int(130 + (100 * intensity))
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))
    
    return bg.convert('RGBA')

def create_template2_overlay(width, height):
    """Create a simple overlay for template 2"""
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Draw decorative elements at top and bottom
    for i in range(20):
        x = i * (width // 20)
        draw.rectangle([x, 0, x + 30, 50], fill=(255, 215, 0, 150))
    
    for i in range(20):
        x = i * (width // 20)
        draw.rectangle(
            [x, height - 50, x + 30, height],
            fill=(255, 105, 180, 150)
        )
    
    # Add text
    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except:
        font = ImageFont.load_default()
    
    text = "Let's Come Together"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
    except:
        text_width = 500
    
    text_x = (width - text_width) // 2
    text_y = 150
    
    # Draw text with shadow
    for dx in [-2, 0, 2]:
        for dy in [-2, 0, 2]:
            if dx != 0 or dy != 0:
                draw.text(
                    (text_x + dx, text_y + dy),
                    text,
                    font=font,
                    fill=(0, 0, 0, 150)
                )
    
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
    
    return overlay

def create_fallback_result(human_image, template_info):
    """Create fallback result for template 1"""
    size = (1080, 1920)
    bg = create_simple_background()
    
    human_resized = resize_to_height(human_image, int(size[1] * 0.75))
    human_width, human_height = human_resized.size
    
    human_y = int(size[1] * 0.70) - human_height
    human_x = (size[0] - human_width) // 2
    
    result = bg.copy()
    result.paste(human_resized, (human_x, human_y), human_resized)
    
    return result

def create_template2_fallback(human_image, template_info):
    """Create fallback result for template 2"""
    size = (1080, 1920)
    bg = create_template2_background()
    
    # Resize human to 75%
    human_resized = resize_image_proportionally(human_image, 0.75)
    human_width, human_height = human_resized.size
    
    # Position at bottom
    human_y = size[1] - human_height
    human_x = (size[0] - human_width) // 2
    
    # Create composite
    result = bg.copy()
    result.paste(human_resized, (human_x, human_y), human_resized)
    
    # Add simple overlay
    overlay = create_template2_overlay(size[0], size[1])
    result.paste(overlay, (0, 0), overlay)
    
    return result

# SAFE MARKDOWN FUNCTION - USE PLAIN TEXT INSTEAD
def safe_text(text):
    """Convert text to safe format without markdown issues"""
    # For now, just return plain text
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - USING PLAIN TEXT TO AVOID MARKDOWN ERRORS"""
    user = update.effective_user
    
    # Add user to database
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # SIMPLE WELCOME MESSAGE WITHOUT MARKDOWN
    welcome_text = f"""
👋 Hello {user.first_name}! ✨

🙏 Welcome to SelamSnap - Christian Photo Editor Bot! 🙏

This bot helps create beautiful images with faith-based templates.

📖 "I can do all things through Christ who strengthens me." - Philippians 4:13

📺 Support Our Ministry:
Subscribe to our YouTube channel:
{DEVELOPER_INFO['youtube']}

🤖 Available Commands:
/upload - Upload a photo and choose template
/developer - Show developer information
/comment - Leave feedback or prayer request
/help - Show all commands

🎨 Features:
• Remove background from photos
• Apply Christian-themed templates
• Simple and easy to use

May God bless you as you use this tool! 🙌
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 Upload Photo", callback_data='upload_photo')],
        [InlineKeyboardButton("👨‍💻 Developer", callback_data='show_developer')],
        [InlineKeyboardButton("💬 Leave Comment", callback_data='leave_comment')],
        [InlineKeyboardButton("📺 YouTube Channel", url=DEVELOPER_INFO['youtube'])]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='HTML'  # NO MARKDOWN PARSING
    )
    if user.id in ADMIN_IDS:
        await update.message.reply_text(
            f"🤖 Bot Server Status:\n"
            f"• Render.com: Online\n"
            f"• PythonAnywhere: Monitoring\n"
            f"• Uptime: {get_uptime()}\n"
            f"• Last ping: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode=None
        )
    # Update user activity
    db.update_user_activity(user.id)

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload command"""
    user = update.effective_user
    db.update_user_activity(user.id)
    
    keyboard = [
        [InlineKeyboardButton("📷 Upload Photo", callback_data='upload_photo')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📤 Upload Your Photo\n\n"
        "Click below to upload a photo.\n"
        "I'll remove the background and let you choose a template.\n\n"
        "🙏 Tip: Send a clear photo with good lighting for best results!",
        reply_markup=reply_markup,
        parse_mode='HTML'  # NO MARKDOWN
    )

async def developer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show developer information"""
    user = update.effective_user
    db.update_user_activity(user.id)
    
    developer_text = f"""
👨‍💻 Developer Information

Name: {DEVELOPER_INFO['name']}
Telegram: {DEVELOPER_INFO['telegram']}
Phone: {DEVELOPER_INFO['phone']}
Email: {DEVELOPER_INFO['email']}

📺 YouTube Channel:
{DEVELOPER_INFO['youtube']}

🙏 About the Developer:
Eyosafit is a Christian developer who creates tools to serve the Christian community. 
All tools are provided free of charge for ministry purposes.

💝 Support the Ministry:
1. Subscribe to our YouTube channel
2. Share this bot with fellow Christians
3. Pray for our ministry

"Whatever you do, work at it with all your heart, as working for the Lord" - Colossians 3:23
    """
    
    keyboard = [
        [InlineKeyboardButton("📺 Subscribe YouTube", url=DEVELOPER_INFO['youtube'])],
        [InlineKeyboardButton("📤 Upload Photo", callback_data='upload_photo')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        developer_text,
        reply_markup=reply_markup,
        parse_mode='HTML'  # NO MARKDOWN
    )

async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comment command - leave feedback or prayer request"""
    user = update.effective_user
    db.update_user_activity(user.id)
    
    context.user_data['awaiting_comment'] = True
    
    keyboard = [
        [InlineKeyboardButton("⭐ 5 Stars", callback_data='rate_5'),
         InlineKeyboardButton("⭐ 4 Stars", callback_data='rate_4')],
        [InlineKeyboardButton("⭐ 3 Stars", callback_data='rate_3'),
         InlineKeyboardButton("⭐ 2 Stars", callback_data='rate_2'),
         InlineKeyboardButton("⭐ 1 Star", callback_data='rate_1')],
        [InlineKeyboardButton("🙏 Prayer Request", callback_data='prayer_request')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💬 Share Your Thoughts\n\n"
        "Please share your feedback, suggestions, or even prayer requests!\n\n"
        "You can:\n"
        "1. Rate our bot (1-5 stars)\n"
        "2. Leave a comment\n"
        "3. Share a prayer request\n\n"
        "First, select a rating or choose 'Prayer Request':",
        reply_markup=reply_markup,
        parse_mode='HTML'  # NO MARKDOWN
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistics command (admin only)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for administrators only.")
        return
    
    stats = db.get_statistics()
    
    stats_text = f"""
📊 Bot Statistics 📊

👥 Users:
• Total Users: {stats['total_users']}
• Active Users (7 days): {stats['active_users']}

📷 Photos Processed:
• Total Photos: {stats['total_photos']}

🎨 Template Usage:
• Template 1 (እገኛለሁ): {stats['template1_used']}
• Template 2 (አብረን እናምልክ): {stats['template2_used']}
• Template 3 (፲፭ ዓመት በ ሉቃስ ፲፭): {stats['template3_used']}

📅 Today's Stats:
"""
    
    if stats['today_stats']:
        today_stats = stats['today_stats']
        stats_text += f"""
• Users Joined: {today_stats[1]}
• Photos Processed: {today_stats[2]}
• Template 1 Used: {today_stats[3]}
• Template 2 Used: {today_stats[4]}
• Template 3 Used: {today_stats[5] if len(today_stats) > 5 else 0}
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 Broadcast", callback_data='admin_broadcast')],
        [InlineKeyboardButton("💬 View Comments", callback_data='admin_comments')],
        [InlineKeyboardButton("🔄 Refresh", callback_data='admin_stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode='HTML'  # NO MARKDOWN
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message command (admin only)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for administrators only.")
        return
    
    if context.args:
        # Send broadcast immediately
        message = ' '.join(context.args)
        await send_broadcast(update, context, message)
    else:
        # Ask for broadcast message
        context.user_data['awaiting_broadcast'] = True
        await update.message.reply_text(
            "📢 Send Broadcast Message\n\n"
            "Please send the message you want to broadcast to all users.\n\n"
            "Format: /broadcast Your message here\n"
            "Or send the message after this prompt.",
            parse_mode='HTML'  # NO MARKDOWN
        )

async def show_comments_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all comments (admin only)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for administrators only.")
        return
    
    comments = db.get_comments()
    
    if not comments:
        await update.message.reply_text("📝 No comments yet.")
        return
    
    comments_text = "📝 User Comments & Prayer Requests\n\n"
    
    for i, (username, comment, rating, timestamp) in enumerate(comments[:20], 1):
        username_display = username or "Anonymous"
        if isinstance(timestamp, str):
            try:
                timestamp_str = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').strftime('%Y-%m-%d %H:%M')
            except:
                timestamp_str = timestamp
        else:
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M') if hasattr(timestamp, 'strftime') else str(timestamp)
        
        if rating > 0:
            stars = "⭐" * rating
            comments_text += f"{i}. {username_display} ({stars})\n"
        else:
            comments_text += f"{i}. {username_display} 🙏 PRAYER REQUEST\n"
        
        # Truncate long comments
        comment_display = comment[:150] + "..." if len(comment) > 150 else comment
        comments_text += f"   {comment_display}\n"
        comments_text += f"   📅 {timestamp_str}\n\n"
    
    await update.message.reply_text(
        comments_text[:4000],
        parse_mode='HTML'  # NO MARKDOWN
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db.update_user_activity(user_id)
    
    if query.data == 'upload_photo':
        await query.edit_message_text(
            "📤 Send me your photo!\n\n"
            "🙏 Important: We remove the background automatically.\n"
            "For best results, send a clear photo with good lighting.\n\n"
            "✅ Recommended: Send as file (not compressed)\n"
            "❌ Avoid: Busy backgrounds, group photos\n\n"
            "Send your photo now:",
            parse_mode='HTML'  # NO MARKDOWN
        )
        user_data[user_id] = {'state': 'awaiting_photo'}
    
    elif query.data == 'show_developer':
        await query.edit_message_text(
            "👨‍💻 Developer Information\n\n"
            "Name: Eyosafit Eliyas\n"
            "Telegram: @eyosafit\n"
            "Phone: +251942594301\n"
            "Email: eyosafit90@gmail.com\n\n"
            "📺 YouTube Channel:\n"
            "https://www.youtube.com/@NU_TECH-v1q\n\n"
            "🙏 Support our ministry by subscribing!",
            parse_mode='HTML'  # NO MARKDOWN
        )
    
    elif query.data == 'leave_comment':
        context.user_data['awaiting_comment'] = True
        keyboard = [
            [InlineKeyboardButton("⭐ 5 Stars", callback_data='rate_5'),
             InlineKeyboardButton("⭐ 4 Stars", callback_data='rate_4')],
            [InlineKeyboardButton("⭐ 3 Stars", callback_data='rate_3'),
             InlineKeyboardButton("⭐ 2 Stars", callback_data='rate_2'),
             InlineKeyboardButton("⭐ 1 Star", callback_data='rate_1')],
            [InlineKeyboardButton("🙏 Prayer Request", callback_data='prayer_request')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💬 Share Your Thoughts\n\n"
            "Please share your feedback, suggestions, or even prayer requests!\n\n"
            "You can:\n"
            "1. Rate our bot (1-5 stars)\n"
            "2. Leave a comment\n"
            "3. Share a prayer request\n\n"
            "First, select a rating or choose 'Prayer Request':",
            reply_markup=reply_markup,
            parse_mode='HTML'  # NO MARKDOWN
        )
    
    elif query.data == 'main_menu':
        # Send new start message
        user = query.from_user
        welcome_text = f"""
👋 Hello {user.first_name}! ✨

🙏 Welcome to SelamSnap - Christian Photo Editor Bot! 🙏

What would you like to do today?
        """
        
        keyboard = [
            [InlineKeyboardButton("📤 Upload Photo", callback_data='upload_photo')],
            [InlineKeyboardButton("👨‍💻 Developer", callback_data='show_developer')],
            [InlineKeyboardButton("💬 Leave Comment", callback_data='leave_comment')],
            [InlineKeyboardButton("📺 YouTube Channel", url=DEVELOPER_INFO['youtube'])]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='HTML'  # NO MARKDOWN
        )
    
    elif query.data.startswith('rate_'):
        rating = int(query.data.split('_')[1])
        context.user_data['rating'] = rating
        await query.edit_message_text(
            f"⭐ Thank you for {rating} star rating!\n\n"
            "Please now type your comment or feedback:\n\n"
            "You can:\n"
            "• Share your experience\n"
            "• Suggest improvements\n"
            "• Give thanks to God\n"
            "• Or just say hello!\n\n"
            "Type your message:",
            parse_mode='HTML'  # NO MARKDOWN
        )
    
    elif query.data == 'prayer_request':
        context.user_data['rating'] = 0  # 0 indicates prayer request
        await query.edit_message_text(
            "🙏 Prayer Request\n\n"
            "Please share your prayer request:\n\n"
            "We will pray for you and your needs.\n"
            "Remember: 'Do not be anxious about anything, but in every situation, by prayer and petition, with thanksgiving, present your requests to God.' - Philippians 4:6\n\n"
            "Type your prayer request:",
            parse_mode='HTML'  # NO MARKDOWN
        )
    
    elif query.data == 'admin_broadcast':
        if user_id in ADMIN_IDS:
            context.user_data['awaiting_broadcast'] = True
            await query.edit_message_text(
                "📢 Admin Broadcast\n\n"
                "Send the message you want to broadcast to all users:",
                parse_mode='HTML'  # NO MARKDOWN
            )
        else:
            await query.answer("⛔ Admin only command", show_alert=True)
    
    elif query.data == 'admin_comments':
        if user_id in ADMIN_IDS:
            comments = db.get_comments()
            if not comments:
                await query.edit_message_text("📝 No comments yet.", parse_mode='HTML')
                return
            
            comments_text = "📝 User Comments & Prayer Requests\n\n"
            for i, (username, comment, rating, timestamp) in enumerate(comments[:10], 1):
                username_display = username or "Anonymous"
                comments_text += f"{i}. {username_display}\n"
                comment_display = comment[:100] + "..." if len(comment) > 100 else comment
                comments_text += f"   {comment_display}\n\n"
            
            await query.edit_message_text(comments_text[:2000], parse_mode='HTML')
        else:
            await query.answer("⛔ Admin only command", show_alert=True)
    
    elif query.data == 'admin_stats':
        if user_id in ADMIN_IDS:
            stats = db.get_statistics()
            stats_text = f"""
📊 Bot Statistics

Users: {stats['total_users']}
Active (7 days): {stats['active_users']}
Photos: {stats['total_photos']}

Template Usage:
1: {stats['template1_used']}
2: {stats['template2_used']}
3: {stats['template3_used']}
"""
            await query.edit_message_text(stats_text, parse_mode='HTML')
        else:
            await query.answer("⛔ Admin only command", show_alert=True)
    
    elif query.data in ['select_template1', 'select_template2', 'select_template3']:
        await handle_template_selection(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user = update.effective_user
    message_text = update.message.text
    
    db.update_user_activity(user.id)
    
    # Check if awaiting comment
    if context.user_data.get('awaiting_comment'):
        rating = context.user_data.get('rating', 0)
        
        # Save comment to database
        success = db.add_comment(
            user_id=user.id,
            username=user.username,
            comment=message_text,
            rating=rating
        )
        
        if success:
            if rating > 0:
                response = f"✅ Thank you for your {rating} star rating and comment!\n\n"
                response += "God bless you! 🙏\n"
                response += "'Let the message of Christ dwell among you richly' - Colossians 3:16"
            else:
                response = "🙏 Thank you for sharing your prayer request!\n\n"
                response += "We will pray for you. Remember:\n"
                response += "'The prayer of a righteous person is powerful and effective.' - James 5:16\n\n"
                response += "May God answer your prayers according to His will. Amen."
        else:
            response = "❌ Sorry, there was an error saving your comment. Please try again."
        
        # Clear the state
        context.user_data.pop('awaiting_comment', None)
        context.user_data.pop('rating', None)
        
        keyboard = [
            [InlineKeyboardButton("📤 Upload Photo", callback_data='upload_photo')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            response,
            reply_markup=reply_markup,
            parse_mode='HTML'  # NO MARKDOWN
        )
    
    # Check if awaiting broadcast (admin only)
    elif context.user_data.get('awaiting_broadcast') and user.id in ADMIN_IDS:
        await send_broadcast(update, context, message_text)
        context.user_data.pop('awaiting_broadcast', None)
    
    else:
        # Handle regular messages
        await update.message.reply_text(
            "🤖 Hello!\n\n"
            "I'm SelamSnap - Christian Photo Editor Bot. Here's what I can do:\n\n"
            "📤 /upload - Upload and edit photos\n"
            "👨‍💻 /developer - Developer information\n"
            "💬 /comment - Leave feedback or prayer request\n"
            "📊 /stats - View statistics (admin)\n"
            "📢 /broadcast - Send message to all users (admin)\n"
            "📝 /showcomments - View all comments (admin)\n"
            "❓ /help - Show help\n\n"
            "May God bless your day! 🙏",
            parse_mode='HTML'  # NO MARKDOWN
        )

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message):
    """Send broadcast message to all users"""
    user = update.effective_user
    
    # Save broadcast to database
    broadcast_id = db.save_broadcast(user.id, message)
    
    # Get all users
    user_ids = db.get_all_users()
    total_users = len(user_ids)
    
    # Send initial message
    progress_msg = await update.message.reply_text(
        f"📢 Starting Broadcast\n\n"
        f"Message: {message[:100]}...\n"
        f"Recipients: {total_users} users\n"
        f"Status: Sending... 0/{total_users}",
        parse_mode='HTML'  # NO MARKDOWN
    )
    
    # Send to users
    sent_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            # Add Christian greeting to broadcast
            broadcast_message = f"🙏 Message from SelamSnap - Christian Photo Editor Bot\n\n{message}\n\nMay the Lord bless you and keep you!"
            
            await context.bot.send_message(
                chat_id=user_id,
                text=broadcast_message,
                parse_mode='HTML'  # NO MARKDOWN
            )
            sent_count += 1
            
            # Update progress every 10 messages
            if sent_count % 10 == 0:
                await progress_msg.edit_text(
                    f"📢 Broadcast in Progress\n\n"
                    f"Message: {message[:100]}...\n"
                    f"Recipients: {total_users} users\n"
                    f"Status: Sending... {sent_count}/{total_users}\n"
                    f"✅ Sent: {sent_count}\n"
                    f"❌ Failed: {failed_count}",
                    parse_mode='HTML'  # NO MARKDOWN
                )
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed_count += 1
    
    # Update broadcast count in database
    db.update_broadcast_count(broadcast_id, sent_count)
    
    # Send completion message
    await progress_msg.edit_text(
        f"✅ Broadcast Complete!\n\n"
        f"Message: {message[:100]}...\n"
        f"Total Recipients: {total_users}\n"
        f"✅ Successfully sent: {sent_count}\n"
        f"❌ Failed: {failed_count}\n\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        parse_mode='HTML'  # NO MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    user = update.effective_user
    db.update_user_activity(user.id)
    
    help_text = """
🙏 SelamSnap - Christian Photo Editor Bot - Help 🙏

🤖 Commands for Everyone:
/start - Start the bot and see welcome message
/upload - Upload a photo for editing
/developer - Show developer information
/comment - Leave feedback, suggestion, or prayer request
/help - Show this help message

🛠 Admin Commands:
/stats - View bot statistics (users, photos, etc.)
/broadcast [message] - Send message to all users
/showcomments - View all user comments and prayer requests

🎨 Available Templates:

1️⃣ እገኛለሁ Template 1 (I Will Come)
   • Removes background automatically
   • Positions person 30% from bottom
   • Adds beautiful cloud decoration
   • Clean, faith-inspired design

2️⃣ አብረን እናምልክ Template (Let's Come Together)
   • Removes background
   • Resizes person appropriately
   • Places at bottom with elegant overlay
   • Perfect for worship themes

3️⃣ ፲፭ ዓመት በ ሉቃስ ፲፭ Template (15 Years in Luke 15)
   • Removes background automatically
   • Positions person 30% from bottom
   • Adds beautiful cloud decoration
   • Clean, faith-inspired design


🙏 For Best Results:
• Send clear photos with good lighting
• Use file upload for better quality
• Single person photos work best
• Simple backgrounds are easier to remove

📖 Bible Verse of the Day:
"And we know that in all things God works for the good of those who love him, who have been called according to his purpose." - Romans 8:28

May God bless you as you use this tool! ✨
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 Upload Photo", callback_data='upload_photo')],
        [InlineKeyboardButton("👨‍💻 Developer", callback_data='show_developer')],
        [InlineKeyboardButton("📺 YouTube Channel", url=DEVELOPER_INFO['youtube'])]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='HTML'  # NO MARKDOWN
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo upload"""
    user_id = update.effective_user.id
    db.update_user_activity(user_id)
    
    photo_file = None
    
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
    elif update.message.document:
        mime_type = update.message.document.mime_type
        if mime_type and 'image' in mime_type:
            photo_file = await update.message.document.get_file()
    
    if photo_file:
        try:
            photo_bytes = await photo_file.download_as_bytearray()
            
            user_data[user_id] = {
                'photo_bytes': bytes(photo_bytes),
                'state': 'selecting_template'
            }
            
            # Show all THREE templates
            keyboard = [
                [InlineKeyboardButton("☁️ እገኛለሁ Template 1", callback_data='select_template1')],
                [InlineKeyboardButton("🤝 አብረን እናምልክ Template", callback_data='select_template2')],
                [InlineKeyboardButton("🌟 ፲፭ ዓመት በ ሉቃስ ፲፭ Template", callback_data='select_template3')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "✅ Photo received!\n\n"
                "Choose a template:\n\n"
                "1. እገኛለሁ \n"
                "2. አብረን እናምልክ\n"
                "3. ፲፭ ዓመት በ ሉቃስ ፲፭\n\n",
                reply_markup=reply_markup,
                parse_mode='HTML'  # NO MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error handling photo: {e}")
            await update.message.reply_text(
                "❌ Error processing your photo. Please try again with /upload"
            )
    else:
        await update.message.reply_text(
            "❌ Please send a valid photo file. Use /upload to try again."
        )

async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle template selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db.update_user_activity(user_id)
    
    user_info = user_data.get(user_id, {})
    
    if not user_info or 'photo_bytes' not in user_info:
        await query.edit_message_text(
            "❌ No photo found. Please start again with /upload"
        )
        return
    
    template_key = query.data.replace('select_', '')
    template_info = TEMPLATES.get(template_key)
    
    if not template_info:
        await query.edit_message_text("❌ Template not available.")
        return
    
    # Show processing message
    template_name = template_info['name']
    processing_msg = await query.edit_message_text(
        f"🔄 Processing: {template_name}\n\n"
        "Step 1: Removing background...",
        parse_mode='HTML'  # NO MARKDOWN
    )
    
    try:
        photo_bytes = user_info['photo_bytes']
        
        await processing_msg.edit_text(
            f"🔄 Processing: {template_name}\n\n"
            "Step 1: Removing background... ✅\n"
            "Step 2: Applying template...",
            parse_mode='HTML'  # NO MARKDOWN
        )
        
        # Extract human
        human_image = extract_human_from_image(photo_bytes)
        
        # Apply appropriate template
        if template_key == 'template1':
            result_image = apply_template1(human_image, template_info)
        elif template_key == 'template2':
            result_image = apply_template2(human_image, template_info)
        elif template_key == 'template3':
            result_image = apply_template3(human_image, template_info)
        else:
            # Default to template 1
            result_image = apply_template1(human_image, template_info)
        
        await processing_msg.edit_text(
            f"🔄 Processing: {template_name}\n\n"
            "Step 1: Removing background... ✅\n"
            "Step 2: Applying template... ✅\n"
            "Step 3: Finalizing...",
            parse_mode='HTML'  # NO MARKDOWN
        )
        
        # Convert to bytes
        img_byte_arr = BytesIO()
        result_image.save(img_byte_arr, format='PNG', optimize=True, quality=95)
        img_byte_arr.seek(0)
        
        # Send result with template-specific caption
        if template_key == 'template1':
            caption = (
                "✨ እገኛለሁ Template Applied!\n\n"
                "Send /upload for another photo!"
            )
        elif template_key == 'template2':
            caption = (
                "✨ አብረን እናምልክ Template Applied!\n\n"
                "Send /upload for another photo!"
            )
        else:  # template3
            caption = (
                "✨ ፲፭ ዓመት በ ሉቃስ ፲፭ Template Applied!\n\n"
                "Send /upload for another photo!"
            )
        
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=img_byte_arr,
            caption=caption,
            parse_mode='HTML'  # NO MARKDOWN
        )
        
        # Update database statistics
        db.increment_photo_count(user_id, template_key)
        
        # Clear user data
        if user_id in user_data:
            user_data[user_id] = {}
        
        # Show options for next step
        keyboard = [
            [InlineKeyboardButton("📸 Another Photo", callback_data='upload_photo')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            f"✅ {template_name} Complete!\n\n"
            "Your photo has been processed successfully.\n"
            "Would you like to process another photo?",
            reply_markup=reply_markup,
            parse_mode='HTML'  # NO MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error processing template {template_key}: {e}")
        await query.edit_message_text(
            f"❌ Error processing with {template_info['name']} template.\n\n"
            "Please try again with /upload\n\n"
            f"Error: {str(e)[:100]}..."
        )

def create_sample_files():
    """Create sample template files if they don't exist"""
    ensure_directories()
    
    # Create sample overlay for template 2 if it doesn't exist
    overlay_path = 'templates/overlay.png'
    if not os.path.exists(overlay_path):
        print("Creating sample overlay.png...")
        overlay = create_template2_overlay(1080, 1920)
        overlay.save(overlay_path)
        print("✅ Created sample overlay.png")
    
    # Create template2 background if it doesn't exist
    template2_bg_path = 'templates/template2_background.png'
    if not os.path.exists(template2_bg_path):
        print("Creating template2_background.png...")
        bg = create_template2_background()
        bg.save(template2_bg_path)
        print("✅ Created template2_background.png")
    
    # Create template3 background if it doesn't exist
    template3_bg_path = 'templates/template3_background.png'
    if not os.path.exists(template3_bg_path):
        print("Creating template3_background.png for template 3...")
        bg = create_template3_background()
        bg.save(template3_bg_path)
        print("✅ Created template3_background.png")

async def send_daily_verse(context: ContextTypes.DEFAULT_TYPE):
    """Send daily Bible verse to all users"""
    try:
        verses = [
            "For God so loved the world that he gave his one and only Son, that whoever believes in him shall not perish but have eternal life. - John 3:16",
            "I can do all this through him who gives me strength. - Philippians 4:13",
            "The Lord is my shepherd, I lack nothing. - Psalm 23:1",
            "Do not be anxious about anything, but in every situation, by prayer and petition, with thanksgiving, present your requests to God. - Philippians 4:6",
            "Trust in the Lord with all your heart and lean not on your own understanding. - Proverbs 3:5"
        ]
        
        import random
        daily_verse = random.choice(verses)
        
        user_ids = db.get_all_users()
        
        for user_id in user_ids:
            try:
                message = f"📖 Daily Bible Verse\n\n{daily_verse}\n\nHave a blessed day! 🙏"
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='HTML'  # NO MARKDOWN
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Failed to send daily verse to {user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in send_daily_verse: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Sorry, an error occurred. Please try again or contact the developer."
            )
    except:
        pass



def run_bot():
    """Run the Telegram bot (for threading)"""
    while True:
        try:
            #TOKEN = '8059796318:AAH_vrqhpEGN8kLPiK05St8RXPsJ-BITf_E'  # Your token
            TOKEN = os.getenv('BOT_TOKEN')
            if not TOKEN:
                logger.error("❌ BOT_TOKEN environment variable not set!")
                print("Please set BOT_TOKEN environment variable")
                return
            # Ensure directories
            ensure_directories()
            
            # Create sample files if needed
            create_sample_files()
            
            # Check required files
            print("🔍 Checking required files...")
            
            print("\n📋 Template 1 Files:")
            for file in ['templates/background.png', 'templates/cloud.png']:
                if os.path.exists(file):
                    print(f"✅ {file}")
                else:
                    print(f"⚠️  {file} - Please add this file")
            
            print("\n📋 Template 2 Files:")
            for file in ['templates/template2_background.png', 'templates/overlay.png']:
                if os.path.exists(file):
                    print(f"✅ {file}")
                else:
                    print(f"⚠️  {file} - Sample created")
            
            print("\n📋 Template 3 Files:")
            for file in ['templates/template3_background.png']:
                if os.path.exists(file):
                    print(f"✅ {file}")
                else:
                    print(f"⚠️  {file} - Sample created")
            
            print("\n🤖 Bot Configuration:")
            print(f"   Admin IDs: {ADMIN_IDS}")
            print("   Database: bot_database.db")
            print("   Template 1: Human 30% from bottom, Cloud 35% from bottom")
            print("   Template 2: Human at bottom (75% size), Overlay on top")
            print("   Template 3: Same as Template 1, different background")
            print(f"   Developer: {DEVELOPER_INFO['name']}")
            print(f"   YouTube: {DEVELOPER_INFO['youtube']}")
            print(f"   Bot Name: SelamSnap - Christian Photo Editor")
        
        # Create application
            print("🤖 Starting SelamSnap Bot on Render...")
            
            # Create application
            application = Application.builder().token(TOKEN).build()
            
            application.add_error_handler(error_handler)
    
            # Add handlers
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("upload", upload_command))
            application.add_handler(CommandHandler("developer", developer_command))
            application.add_handler(CommandHandler("comment", comment_command))
            application.add_handler(CommandHandler("stats", stats_command))
            application.add_handler(CommandHandler("broadcast", broadcast_command))
            application.add_handler(CommandHandler("showcomments", show_comments_command))
            application.add_handler(CommandHandler("help", help_command))
            
            application.add_handler(CallbackQueryHandler(button_handler))
            
            application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            
            # Run bot
            application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            print(f"⚠️ Restarting bot in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    # Start keep-alive
    keep_alive.start()
    
    # Start Flask server on port 10000 (Render default)
    port = int(os.getenv('PORT', 10000))
    
    # Start bot in background thread
    import threading

    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    
    print(f"🌐 Flask server started on port {port}")
    
    # Start Flask app
    print(f"🚀 Starting Flask server on port {port}")
    print(f"🔗 Render URL: {RENDER_URL}")
    print(f"🔗 PythonAnywhere URL: {PYTHONANYWHERE_URL}")
    print(f"⏰ Keep-alive interval: 14 minutes")
    
    app.run(host='0.0.0.0', port=port, debug=False)
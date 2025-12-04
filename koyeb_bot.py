
import os
import asyncio
import logging
import time
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ============================================================================
# CONFIGURATION
# ============================================================================

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '8253530670:AAFXSKii0neNFnadDP39lg8JUjlQDLqOMxY')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

# Developer info
DEVELOPER_INFO = {
    'name': 'Eyosafit Eliyas',
    'telegram': '@eyosafit',
    'phone': '+251942594301',
    'email': 'eyosafit90@gmail.com',
    'youtube': 'https://www.youtube.com/@NU_TECH-v1q'
}

print("=" * 60)
print("🤖 SELAMSNAP BOT STARTING")
print("=" * 60)

# Try to import rembg with memory optimization
try:
    from rembg import new_session
    REMBG_AVAILABLE = True
    print("✅ rembg loaded successfully")
    
    # Initialize session with smaller model (pre-downloaded in Docker)
    try:
        session = new_session("u2netp")
        print("✅ Using u2netp model (54MB, pre-downloaded)")
    except Exception as e:
        print(f"⚠️ Could not load u2netp: {e}")
        try:
            session = new_session()
            print("⚠️ Using default model (fallback)")
        except:
            session = None
            print("❌ Could not initialize any model")
            
except ImportError as e:
    REMBG_AVAILABLE = False
    session = None
    print(f"❌ rembg not available: {e}")

# Template configuration
TEMPLATES: Dict = {
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

# Store user data temporarily
user_data: Dict = {}

# ============================================================================
# DATABASE
# ============================================================================

class Database:
    def __init__(self):
        self.conn = None
        self.setup_database()
    
    def setup_database(self):
        """Initialize database and create tables"""
        self.conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TEXT,
                photo_count INTEGER DEFAULT 0,
                last_active TEXT,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')
        
        # Statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                date TEXT PRIMARY KEY,
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
                timestamp TEXT
            )
        ''')
        
        # Broadcast messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message TEXT,
                timestamp TEXT,
                sent_count INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()
        print("✅ Database initialized")
    
    def add_user(self, user_id, username, first_name, last_name):
        """Add new user to database"""
        cursor = self.conn.cursor()
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, join_date, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, now, now))
            
            # Update statistics for today
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('INSERT OR IGNORE INTO statistics (date) VALUES (?)', (today,))
            cursor.execute('UPDATE statistics SET users_joined = users_joined + 1 WHERE date = ?', (today,))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def update_user_activity(self, user_id):
        """Update user's last activity time"""
        cursor = self.conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', (now, user_id))
        self.conn.commit()
    
    def increment_photo_count(self, user_id, template_key):
        """Increment user's photo count and template usage"""
        cursor = self.conn.cursor()
        
        # Update user's photo count
        cursor.execute('UPDATE users SET photo_count = photo_count + 1 WHERE user_id = ?', (user_id,))
        
        # Update statistics
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('UPDATE statistics SET photos_processed = photos_processed + 1 WHERE date = ?', (today,))
        
        # Update template-specific statistics
        template_map = {
            'template1': 'template1_used',
            'template2': 'template2_used', 
            'template3': 'template3_used'
        }
        
        if template_key in template_map:
            column = template_map[template_key]
            cursor.execute(f'UPDATE statistics SET {column} = {column} + 1 WHERE date = ?', (today,))
        
        self.conn.commit()
    
    def add_comment(self, user_id, username, comment, rating):
        """Add user comment"""
        cursor = self.conn.cursor()
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO comments (user_id, username, comment, rating, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, comment, rating, now))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            return False
    
    def get_comments(self, limit=50):
        """Get all comments (admin only)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT username, comment, rating, timestamp FROM comments ORDER BY timestamp DESC LIMIT ?', (limit,))
        return cursor.fetchall()
    
    def get_statistics(self, days=30):
        """Get statistics for the last N days"""
        cursor = self.conn.cursor()
        
        # Get total users
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Get active users (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('SELECT COUNT(*) FROM users WHERE last_active > ?', (week_ago,))
        active_users = cursor.fetchone()[0]
        
        # Get total photos processed
        cursor.execute('SELECT SUM(photo_count) FROM users')
        total_photos = cursor.fetchone()[0] or 0
        
        # Get today's statistics
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT * FROM statistics WHERE date = ?', (today,))
        today_stats = cursor.fetchone()
        
        # Get template usage
        cursor.execute('SELECT SUM(template1_used), SUM(template2_used), SUM(template3_used) FROM statistics')
        template_usage = cursor.fetchone()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_photos': total_photos,
            'today_stats': today_stats,
            'template1_used': template_usage[0] or 0 if template_usage else 0,
            'template2_used': template_usage[1] or 0 if template_usage else 0,
            'template3_used': template_usage[2] or 0 if template_usage and len(template_usage) > 2 else 0
        }
    
    def save_broadcast(self, admin_id, message):
        """Save broadcast message"""
        cursor = self.conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO broadcasts (admin_id, message, timestamp) VALUES (?, ?, ?)', (admin_id, message, now))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_broadcast_count(self, broadcast_id, count):
        """Update broadcast sent count"""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE broadcasts SET sent_count = ? WHERE id = ?', (count, broadcast_id))
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

# ============================================================================
# IMAGE PROCESSING FUNCTIONS
# ============================================================================

def ensure_directories():
    """Ensure all required directories exist"""
    directories = ['templates', 'temp']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def extract_human_from_image(image_bytes):
    """Remove background using rembg or fallback"""
    if REMBG_AVAILABLE and session:
        try:
            from rembg import remove
            input_image = Image.open(BytesIO(image_bytes)).convert("RGBA")
            input_array = np.array(input_image)
            
            # Use memory-efficient settings
            output_array = remove(
                input_array,
                session=session,
                alpha_matting=False,  # Disable to save memory
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10
            )
            
            return Image.fromarray(output_array)
            
        except Exception as e:
            logger.error(f"Error with rembg: {e}")
            return simple_background_removal(image_bytes)
    else:
        return simple_background_removal(image_bytes)

def simple_background_removal(image_bytes):
    """Simple background removal fallback"""
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGBA")
        width, height = image.size
        
        # Create a simple circular mask (assumes person is in center)
        mask = Image.new('L', (width, height), 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw ellipse covering most of the image
        margin = min(width, height) * 0.1
        draw.ellipse([
            margin, margin,
            width - margin, height - margin
        ], fill=255)
        
        # Apply slight blur to edges
        mask = mask.filter(ImageFilter.GaussianBlur(radius=10))
        
        # Apply mask
        image.putalpha(mask)
        return image
    except Exception as e:
        logger.error(f"Error in simple extraction: {e}")
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

def create_simple_background():
    """Create a simple background for template 1"""
    size = (1080, 1920)
    bg = Image.new('RGB', size, (25, 42, 86))
    return bg.convert('RGBA')

def create_template2_background():
    """Create a background for template 2"""
    size = (1080, 1920)
    bg = Image.new('RGB', size, (30, 60, 90))
    return bg.convert('RGBA')

def create_template3_background():
    """Create an alternative background for template 3"""
    size = (1080, 1920)
    bg = Image.new('RGB', size, (75, 0, 130))
    return bg.convert('RGBA')

def create_template2_overlay(width, height):
    """Create a simple overlay for template 2"""
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    return overlay

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
        
        # Load cloud if exists
        cloud_path = template_info['elements'].get('cloud')
        if cloud_path and os.path.exists(cloud_path):
            cloud = Image.open(cloud_path).convert('RGBA')
            cloud_target_width = int(template_width * 0.8)
            cloud_target_height = int(cloud.height * (cloud_target_width / cloud.width))
            cloud = cloud.resize((cloud_target_width, cloud_target_height), Image.Resampling.LANCZOS)
            
            cloud_position_y = template_info['elements'].get('cloud_position_y', 0.35)
            cloud_y = int(template_height * (1 - cloud_position_y) - cloud_target_height)
            cloud_x = (template_width - cloud_target_width) // 2
        else:
            cloud = None
        
        # Create composite
        composite = template.copy()
        composite.paste(human_resized, (human_x, human_y), human_resized)
        
        if cloud:
            composite.paste(cloud, (cloud_x, cloud_y), cloud)
        
        return composite
        
    except Exception as e:
        logger.error(f"Error applying template 1: {e}")
        return human_image

def apply_template2(human_image, template_info):
    """Apply template 2 - Human at bottom with overlay on top"""
    try:
        template_path = template_info['template_image']
        if os.path.exists(template_path):
            template = Image.open(template_path).convert('RGBA')
        else:
            template = create_template2_background()
        
        template_width, template_height = template.size
        
        # Resize human
        human_scale = template_info['elements'].get('human_size', 0.75)
        human_resized = resize_image_proportionally(human_image, human_scale)
        
        # Position at bottom
        human_width, human_height = human_resized.size
        human_y = template_height - human_height
        human_x = (template_width - human_width) // 2
        
        # Create composite
        composite = template.copy()
        composite.paste(human_resized, (human_x, human_y), human_resized)
        
        return composite
        
    except Exception as e:
        logger.error(f"Error applying template 2: {e}")
        return human_image

def apply_template3(human_image, template_info):
    """Apply template 3 - Same as template 1"""
    return apply_template1(human_image, template_info)

def create_sample_files():
    """Create sample template files if they don't exist"""
    ensure_directories()
    
    # Only create if they don't exist
    files_to_create = [
        ('templates/overlay.png', create_template2_overlay(1080, 1920)),
        ('templates/template2_background.png', create_template2_background()),
        ('templates/template3_background.png', create_template3_background()),
        ('templates/background.png', create_simple_background())
    ]
    
    for file_path, image in files_to_create:
        if not os.path.exists(file_path):
            image.save(file_path)
            print(f"✅ Created {file_path}")

# ============================================================================
# TELEGRAM BOT HANDLERS
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    
    # Add user to database
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
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
        parse_mode='HTML'
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
        parse_mode='HTML'
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
        parse_mode='HTML'
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
        parse_mode='HTML'
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
        parse_mode='HTML'
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
            parse_mode='HTML'
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
        parse_mode='HTML'
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
        parse_mode='HTML'
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
            parse_mode='HTML'
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
            parse_mode='HTML'
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
            parse_mode='HTML'
        )
    
    elif query.data == 'main_menu':
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
            parse_mode='HTML'
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
            parse_mode='HTML'
        )
    
    elif query.data == 'prayer_request':
        context.user_data['rating'] = 0
        await query.edit_message_text(
            "🙏 Prayer Request\n\n"
            "Please share your prayer request:\n\n"
            "We will pray for you and your needs.\n"
            "Remember: 'Do not be anxious about anything, but in every situation, by prayer and petition, with thanksgiving, present your requests to God.' - Philippians 4:6\n\n"
            "Type your prayer request:",
            parse_mode='HTML'
        )
    
    elif query.data == 'admin_broadcast':
        if user_id in ADMIN_IDS:
            context.user_data['awaiting_broadcast'] = True
            await query.edit_message_text(
                "📢 Admin Broadcast\n\n"
                "Send the message you want to broadcast to all users:",
                parse_mode='HTML'
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
            parse_mode='HTML'
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
            parse_mode='HTML'
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
                parse_mode='HTML'
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
        parse_mode='HTML'
    )
    
    try:
        photo_bytes = user_info['photo_bytes']
        
        await processing_msg.edit_text(
            f"🔄 Processing: {template_name}\n\n"
            "Step 1: Removing background... ✅\n"
            "Step 2: Applying template...",
            parse_mode='HTML'
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
            parse_mode='HTML'
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
            parse_mode='HTML'
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
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error processing template {template_key}: {e}")
        await query.edit_message_text(
            f"❌ Error processing with {template_info['name']} template.\n\n"
            "Please try again with /upload\n\n"
            f"Error: {str(e)[:100]}..."
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
        parse_mode='HTML'
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
                parse_mode='HTML'
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
                    parse_mode='HTML'
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
        parse_mode='HTML'
    )

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

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main entry point"""
    print("=" * 60)
    print("🤖 SELAMSNAP - CHRISTIAN PHOTO EDITOR BOT")
    print("🚀 Starting on Koyeb (Standalone Mode)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Ensure directories and create sample files
    ensure_directories()
    create_sample_files()
    model_path = "/root/.u2net/u2netp.onnx"
    if os.path.exists(model_path):
        size = os.path.getsize(model_path) / (1024 * 1024)
        print(f"✅ Model found: {model_path}")
        print(f"📊 Model size: {size:.1f}MB")
    else:
        print("⚠️ Model not found at expected location")
    # Check required files
    print("\n🔍 Checking required files...")
    
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
    print(f"   Developer: {DEVELOPER_INFO['name']}")
    print(f"   YouTube: {DEVELOPER_INFO['youtube']}")
    print("   Mode: Polling (No Flask Server)")
    
    # Run bot with retry logic
    while True:
        try:
            print("\n" + "=" * 60)
            print("✅ Starting Telegram Bot with polling...")
            print("=" * 60)
            
            # Create application
            application = Application.builder().token(BOT_TOKEN).build()
            
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
            print("✅ Bot is running and ready to receive messages...")
            print("📱 Send /start to your bot to test")
            print("=" * 60 + "\n")
            
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                close_loop=False
            )
            
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            print(f"\n⚠️ Bot crashed. Restarting in 10 seconds...")
            print(f"Error: {str(e)[:200]}")
            time.sleep(10)

if __name__ == '__main__':
    main()

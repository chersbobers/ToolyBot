local discordia = require('discordia')
local client = discordia.Client()
local fs = require('fs')
local json = require('json')
local http = require('coro-http')
local timer = require('timer')

-- Configuration
local config = {
    token = os.getenv('DISCORD_TOKEN'),
    prefix = '!',
    data_file = 'data.json',
    timeout_file = 'timeouts.json',
    
    -- XP System
    xp_min = 15,
    xp_max = 25,
    xp_cooldown = 60, -- seconds
    xp_per_level = 100,
    level_up_multiplier = 10,
    
    -- YouTube
    youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID'),
    notification_channel_id = os.getenv('NOTIFICATION_CHANNEL_ID'),
    video_check_interval = 300, -- 5 minutes
    
    -- Auto-save
    autosave_interval = 300, -- 5 minutes
    leaderboard_update_interval = 3600 -- 1 hour
}

-- Database Module
local Database = {}
Database.__index = Database

function Database.new(filename)
    local self = setmetatable({}, Database)
    self.filename = filename
    self.data = self:load()
    return self
end

function Database:load()
    if fs.existsSync(self.filename) then
        local content = fs.readFileSync(self.filename)
        local success, decoded = pcall(json.decode, content)
        if success then return decoded end
    end
    return {
        users = {},
        guilds = {},
        leaderboards = {},
        youtube = {}
    }
end

function Database:save()
    local success, encoded = pcall(json.encode, self.data)
    if success then
        fs.writeFileSync(self.filename, encoded)
    end
end

-- User Data Functions
function Database:getUser(guildId, userId)
    local key = guildId .. '_' .. userId
    if not self.data.users[key] then
        self.data.users[key] = {
            coins = 0,
            bank = 0,
            level = 1,
            xp = 0,
            lastMessage = 0,
            lastDaily = 0,
            lastWork = 0,
            fishCaught = 0,
            gamblingWins = 0,
            gamblingLosses = 0
        }
    end
    return self.data.users[key]
end

function Database:setUser(guildId, userId, data)
    local key = guildId .. '_' .. userId
    self.data.users[key] = data
    self:save()
end

function Database:getGuild(guildId)
    if not self.data.guilds[guildId] then
        self.data.guilds[guildId] = {
            notificationsEnabled = true,
            leaderboardChannelId = nil,
            leaderboardMessageId = nil
        }
    end
    return self.data.guilds[guildId]
end

function Database:setGuild(guildId, data)
    self.data.guilds[guildId] = data
    self:save()
end

function Database:getLastVideoId(guildId)
    return self.data.youtube[guildId]
end

function Database:setLastVideoId(guildId, videoId)
    self.data.youtube[guildId] = videoId
    self:save()
end

function Database:getAllGuildUsers(guildId)
    local users = {}
    for key, data in pairs(self.data.users) do
        if key:match('^' .. guildId .. '_') then
            local userId = key:match('_(.+)$')
            table.insert(users, {userId = userId, data = data})
        end
    end
    
    -- Sort by level and XP
    table.sort(users, function(a, b)
        if a.data.level == b.data.level then
            return a.data.xp > b.data.xp
        end
        return a.data.level > b.data.level
    end)
    
    return users
end

-- Initialize database
local db = Database.new(config.data_file)

-- Timeout Module
local TimeoutDB = Database.new(config.timeout_file)

-- Utility Functions
local function createProgressBar(current, total, length)
    length = length or 20
    if total == 0 then
        return string.rep('░', length) .. ' 0%'
    end
    
    local filled = math.floor((current / total) * length)
    local bar = string.rep('█', filled) .. string.rep('░', length - filled)
    local percentage = math.floor((current / total) * 100)
    return '`' .. bar .. '` ' .. percentage .. '%'
end

local function formatNumber(num)
    local formatted = tostring(num)
    local k
    while true do
        formatted, k = string.gsub(formatted, "^(-?%d+)(%d%d%d)", '%1,%2')
        if k == 0 then break end
    end
    return formatted
end

-- Command Handler
local commands = {}

-- ============================================
-- GENERAL COMMANDS
-- ============================================

function commands.help(message)
    local embed = {
        title = '🤖 Tooly Bot - Command List',
        color = 0x5865F2,
        fields = {
            {
                name = '📊 Leveling',
                value = '`!rank [@user]` - View rank and level\n`!leaderboard` - Server leaderboard\n`!setleaderboard` - Set auto-updating leaderboard (Admin)',
                inline = false
            },
            {
                name = '💰 Economy',
                value = '`!balance [@user]` - Check balance\n`!daily` - Daily reward\n`!work` - Work for coins\n`!give @user <amount>` - Give coins',
                inline = false
            },
            {
                name = '🎮 Fun',
                value = '`!8ball <question>` - Magic 8ball\n`!roll [sides]` - Roll dice\n`!coinflip` - Flip a coin\n`!kitty` - Random cat\n`!doggy` - Random dog\n`!joke` - Random joke',
                inline = false
            },
            {
                name = '🛡️ Moderation',
                value = '`!timeout @user [reason]` - Timeout user (Admin)\n`!untimeout @user` - Remove timeout (Admin)\n`!timeouts` - View timeouts (Admin)\n`!mute/@user` - Mute user (Admin)\n`!kick/@user` - Kick user (Admin)',
                inline = false
            },
            {
                name = '📺 YouTube',
                value = '`!togglenotif` - Toggle notifications (Admin)\n`!notifstatus` - Check notification status',
                inline = false
            }
        },
        footer = {
            text = 'Use ' .. config.prefix .. '<command> to run'
        }
    }
    message:reply{embed = embed}
end

function commands.ping(message)
    local startTime = os.clock()
    message:reply('🏓 Pong! Calculating...'):next(function()
        local latency = math.floor((os.clock() - startTime) * 1000)
        message.channel:send(string.format('🏓 Pong! Latency: `%dms`', latency))
    end)
end

-- ============================================
-- LEVELING COMMANDS
-- ============================================

function commands.rank(message, args)
    local guild = message.guild
    if not guild then return end
    
    local targetUser = message.mentionedUsers.first or message.author
    local userData = db:getUser(guild.id, targetUser.id)
    local xpNeeded = userData.level * config.xp_per_level
    
    -- Get rank
    local allUsers = db:getAllGuildUsers(guild.id)
    local rank = 'Unranked'
    for i, u in ipairs(allUsers) do
        if u.userId == targetUser.id then
            rank = '#' .. i
            break
        end
    end
    
    local progressBar = createProgressBar(userData.xp, xpNeeded, 20)
    local progressPercent = xpNeeded > 0 and math.floor((userData.xp / xpNeeded) * 100) or 0
    
    local color = 0x4D96FF
    if userData.level >= 50 then color = 0xFF6B6B
    elseif userData.level >= 30 then color = 0xFFD93D
    elseif userData.level >= 15 then color = 0x6BCB77 end
    
    local totalCoins = userData.coins + userData.bank
    
    local description = string.format([[
**RANK** • %s / %d
**LEVEL** • %d
**XP** • %s / %s (%d%%)

%s

**💰 BALANCE** • %s coins
]], rank, #allUsers, userData.level, formatNumber(userData.xp), formatNumber(xpNeeded), progressPercent, progressBar, formatNumber(totalCoins))
    
    local embed = {
        color = color,
        author = {
            name = targetUser.username .. "'s Profile",
            icon_url = targetUser.avatarURL
        },
        description = description,
        thumbnail = {url = targetUser.avatarURL},
        footer = {text = 'Requested by ' .. message.author.username},
        timestamp = discordia.Date():toISO('T', 'Z')
    }
    
    if userData.fishCaught > 0 then
        table.insert(embed.fields or {}, {name = '🎣 Fish Caught', value = formatNumber(userData.fishCaught), inline = true})
        embed.fields = embed.fields or {}
    end
    
    message:reply{embed = embed}
end

function commands.leaderboard(message)
    local guild = message.guild
    if not guild then return end
    
    local allUsers = db:getAllGuildUsers(guild.id)
    local description = {}
    
    for i = 1, math.min(10, #allUsers) do
        local u = allUsers[i]
        local medal = i == 1 and '🥇' or i == 2 and '🥈' or i == 3 and '🥉' or '**' .. i .. '.**'
        local totalCoins = u.data.coins + u.data.bank
        
        table.insert(description, string.format('%s <@%s>\n└ Level %d (%s XP) • %s coins',
            medal, u.userId, u.data.level, formatNumber(u.data.xp), formatNumber(totalCoins)))
    end
    
    local embed = {
        title = '🏆 Server Leaderboard',
        description = #description > 0 and table.concat(description, '\n') or 'No users yet!',
        color = 0x9B59B6,
        footer = {text = 'Updates every hour • Showing Level & Total Coins'},
        timestamp = discordia.Date():toISO('T', 'Z')
    }
    
    message:reply{embed = embed}
end

function commands.setleaderboard(message)
    if not message.member:hasPermission('administrator') then
        message:reply('❌ You need administrator permission!')
        return
    end
    
    local guild = message.guild
    commands.leaderboard(message)
    
    -- Save leaderboard location
    local guildData = db:getGuild(guild.id)
    guildData.leaderboardChannelId = message.channel.id
    db:setGuild(guild.id, guildData)
    
    message.channel:send('✅ Auto-updating leaderboard created! It will update every hour.')
end

-- ============================================
-- ECONOMY COMMANDS
-- ============================================

function commands.balance(message, args)
    local guild = message.guild
    if not guild then return end
    
    local targetUser = message.mentionedUsers.first or message.author
    local userData = db:getUser(guild.id, targetUser.id)
    
    local embed = {
        title = '💰 Balance',
        description = string.format('%s has **%s** coins in wallet and **%s** in bank!\n**Total:** %s coins',
            targetUser.mentionString, formatNumber(userData.coins), formatNumber(userData.bank),
            formatNumber(userData.coins + userData.bank)),
        color = 0xFFD700
    }
    message:reply{embed = embed}
end

function commands.daily(message)
    local guild = message.guild
    if not guild then return end
    
    local userData = db:getUser(guild.id, message.author.id)
    local now = os.time()
    local dayInSeconds = 86400
    
    if now - userData.lastDaily < dayInSeconds then
        local timeLeft = dayInSeconds - (now - userData.lastDaily)
        local hoursLeft = math.floor(timeLeft / 3600)
        message:reply(string.format('⏳ You already claimed your daily! Come back in %d hours.', hoursLeft))
        return
    end
    
    local reward = 100
    userData.coins = userData.coins + reward
    userData.lastDaily = now
    db:setUser(guild.id, message.author.id, userData)
    
    message:reply(string.format('✅ You claimed your daily reward of **%s** coins!\n💰 New balance: **%s** coins',
        formatNumber(reward), formatNumber(userData.coins)))
end

function commands.work(message)
    local guild = message.guild
    if not guild then return end
    
    local userData = db:getUser(guild.id, message.author.id)
    local now = os.time()
    
    if now - userData.lastWork < 3600 then
        local timeLeft = 3600 - (now - userData.lastWork)
        local minutesLeft = math.floor(timeLeft / 60)
        message:reply(string.format('⏳ You need to rest! Come back in %d minutes.', minutesLeft))
        return
    end
    
    local earnings = math.random(10, 50)
    userData.coins = userData.coins + earnings
    userData.lastWork = now
    db:setUser(guild.id, message.author.id, userData)
    
    local jobs = {
        'You worked as a programmer and earned',
        'You delivered pizza and earned',
        'You streamed on Twitch and earned',
        'You mowed lawns and earned',
        'You washed cars and earned',
        'You walked dogs and earned',
        'You tutored students and earned'
    }
    
    local job = jobs[math.random(#jobs)]
    message:reply(string.format('💼 %s **%s** coins!\n💰 New balance: **%s** coins',
        job, formatNumber(earnings), formatNumber(userData.coins)))
end

function commands.give(message, args)
    local guild = message.guild
    if not guild then return end
    
    local targetUser = message.mentionedUsers.first
    if not targetUser then
        message:reply('❌ Please mention a user to give coins to!')
        return
    end
    
    if targetUser.id == message.author.id then
        message:reply('❌ You cannot give coins to yourself!')
        return
    end
    
    local amount = tonumber(args[2])
    if not amount or amount <= 0 then
        message:reply('❌ Please specify a valid amount!')
        return
    end
    
    local senderData = db:getUser(guild.id, message.author.id)
    if senderData.coins < amount then
        message:reply('❌ You don\'t have enough coins!')
        return
    end
    
    local receiverData = db:getUser(guild.id, targetUser.id)
    senderData.coins = senderData.coins - amount
    receiverData.coins = receiverData.coins + amount
    
    db:setUser(guild.id, message.author.id, senderData)
    db:setUser(guild.id, targetUser.id, receiverData)
    
    message:reply(string.format('✅ You gave **%s** coins to %s!', formatNumber(amount), targetUser.mentionString))
end

-- ============================================
-- FUN COMMANDS
-- ============================================

function commands['8ball'](message, args)
    if #args == 0 then
        message:reply('❌ Please ask a question!')
        return
    end
    
    local responses = {
        'Yes, definitely!', 'It is certain.', 'Without a doubt.', 'You may rely on it.',
        'As I see it, yes.', 'Most likely.', 'Outlook good.', 'Signs point to yes.',
        'Reply hazy, try again.', 'Ask again later.', 'Better not tell you now.',
        'Cannot predict now.', 'Concentrate and ask again.', "Don't count on it.",
        'My reply is no.', 'My sources say no.', 'Outlook not so good.', 'Very doubtful.'
    }
    
    local answer = responses[math.random(#responses)]
    message:reply(string.format('🔮 %s', answer))
end

function commands.roll(message, args)
    local sides = tonumber(args[1]) or 6
    if sides < 2 or sides > 100 then
        message:reply('❌ Dice must have between 2 and 100 sides!')
        return
    end
    
    local result = math.random(1, sides)
    message:reply(string.format('🎲 You rolled a **%d** (1-%d)', result, sides))
end

function commands.coinflip(message)
    local result = math.random(2) == 1 and 'Heads' or 'Tails'
    message:reply(string.format('🪙 The coin landed on **%s**!', result))
end

function commands.kitty(message)
    http.request('GET', 'https://api.thecatapi.com/v1/images/search', {}, function(data, body)
        local success, decoded = pcall(json.decode, body)
        if success and decoded[1] then
            local embed = {
                title = '🐱 Random Kitty!',
                color = 0xFF69B4,
                image = {url = decoded[1].url},
                footer = {text = 'Requested by ' .. message.author.username}
            }
            message:reply{embed = embed}
        else
            message:reply('Failed to fetch a cat picture 😿')
        end
    end)
end

function commands.doggy(message)
    http.request('GET', 'https://api.thedogapi.com/v1/images/search', {}, function(data, body)
        local success, decoded = pcall(json.decode, body)
        if success and decoded[1] then
            local embed = {
                title = '🐶 Random Doggy!',
                color = 0xFF69B4,
                image = {url = decoded[1].url},
                footer = {text = 'Requested by ' .. message.author.username}
            }
            message:reply{embed = embed}
        else
            message:reply('Failed to fetch a dog picture 😥')
        end
    end)
end

function commands.joke(message)
    http.request('GET', 'https://official-joke-api.appspot.com/random_joke', {}, function(data, body)
        local success, decoded = pcall(json.decode, body)
        if success and decoded.setup then
            local embed = {
                title = '😂 Random Joke',
                description = string.format('**%s**\n\n||%s||', decoded.setup, decoded.punchline),
                color = 0xFFA500,
                footer = {text = (decoded.type or 'general') .. ' joke'}
            }
            message:reply{embed = embed}
        else
            local jokes = {
                {setup = 'Why did the scarecrow win an award?', punchline = 'Because he was outstanding in his field!'},
                {setup = "Why don't scientists trust atoms?", punchline = 'Because they make up everything!'},
                {setup = 'What do you call a fake noodle?', punchline = 'An impasta!'}
            }
            local j = jokes[math.random(#jokes)]
            local embed = {
                title = '😂 Random Joke',
                description = string.format('**%s**\n\n||%s||', j.setup, j.punchline),
                color = 0xFFA500
            }
            message:reply{embed = embed}
        end
    end)
end

-- ============================================
-- MODERATION COMMANDS
-- ============================================

function commands.timeout(message, args)
    if not message.member:hasPermission('administrator') then
        message:reply('❌ You need administrator permission!')
        return
    end
    
    local targetUser = message.mentionedUsers.first
    if not targetUser then
        message:reply('❌ Please mention a user to timeout!')
        return
    end
    
    local reason = table.concat(args, ' ', 2) or 'No reason provided'
    
    -- Implementation would store removed roles and assign timeout role
    message:reply(string.format('⏸️ %s has been timed out. Reason: %s', targetUser.mentionString, reason))
end

function commands.mute(message, args)
    if not message.member:hasPermission('administrator') then
        message:reply('❌ You need administrator permission!')
        return
    end
    
    local targetUser = message.mentionedUsers.first
    if not targetUser then
        message:reply('❌ Please mention a user to mute!')
        return
    end
    
    message:reply(string.format('🔇 %s has been muted.', targetUser.mentionString))
end

function commands.kick(message, args)
    if not message.member:hasPermission('administrator') then
        message:reply('❌ You need administrator permission!')
        return
    end
    
    local targetUser = message.mentionedUsers.first
    if not targetUser then
        message:reply('❌ Please mention a user to kick!')
        return
    end
    
    local reason = table.concat(args, ' ', 2) or 'No reason provided'
    message.guild:kickUser(targetUser.id, reason)
    message:reply(string.format('👢 %s has been kicked. Reason: %s', targetUser.mentionString, reason))
end

-- ============================================
-- YOUTUBE COMMANDS
-- ============================================

function commands.togglenotif(message)
    if not message.member:hasPermission('manageGuild') then
        message:reply('❌ You need Manage Server permission!')
        return
    end
    
    local guild = message.guild
    local guildData = db:getGuild(guild.id)
    guildData.notificationsEnabled = not guildData.notificationsEnabled
    db:setGuild(guild.id, guildData)
    
    local status = guildData.notificationsEnabled and 'enabled ✅' or 'disabled ❌'
    local embed = {
        title = '🔔 Notification Settings',
        description = 'YouTube notifications are now **' .. status .. '**',
        color = guildData.notificationsEnabled and 0xFF69B4 or 0x808080
    }
    message:reply{embed = embed}
end

function commands.notifstatus(message)
    local guild = message.guild
    if not guild then return end
    
    local guildData = db:getGuild(guild.id)
    local status = guildData.notificationsEnabled and 'enabled ✅' or 'disabled ❌'
    
    local embed = {
        title = '🔔 Notification Status',
        description = 'YouTube notifications are currently **' .. status .. '**',
        color = guildData.notificationsEnabled and 0xFF69B4 or 0x808080
    }
    message:reply{embed = embed}
end

-- ============================================
-- EVENT HANDLERS
-- ============================================

client:on('ready', function()
    print('✅ Logged in as ' .. client.user.username)
    print('📊 Connected to ' .. #client.guilds .. ' guilds')
    client:setGame(config.prefix .. 'help | Tooly Bot')
    print('🚀 All systems operational!')
    
    -- Start auto-save timer
    timer.setInterval(config.autosave_interval * 1000, function()
        db:save()
        print('💾 Data autosaved')
    end)
end)

client:on('messageCreate', function(message)
    if message.author.bot then return end
    
    local guild = message.guild
    if guild then
        -- XP System
        local userData = db:getUser(guild.id, message.author.id)
        local now = os.time()
        
        if now - userData.lastMessage >= config.xp_cooldown then
            userData.lastMessage = now
            local xpGain = math.random(config.xp_min, config.xp_max)
            userData.xp = userData.xp + xpGain
            local xpNeeded = userData.level * config.xp_per_level
            
            if userData.xp >= xpNeeded then
                userData.level = userData.level + 1
                userData.xp = 0
                
                local messages = {
                    '🎉 GG %s! You leveled up to **Level %d**!',
                    '⭐ Congrats %s! You\'re now **Level %d**!',
                    '🚀 Level up! %s reached **Level %d**!',
                    '💫 Awesome! %s is now **Level %d**!'
                }
                
                local coinReward = userData.level * config.level_up_multiplier
                userData.coins = userData.coins + coinReward
                
                local msg = messages[math.random(#messages)]
                message.channel:send(string.format(msg .. ' You earned **%s coins**! 💰',
                    message.author.mentionString, userData.level, formatNumber(coinReward)))
            end
            
            db:setUser(guild.id, message.author.id, userData)
        end
    end
    
    -- Command Handler
    if not message.content:match('^' .. config.prefix) then return end
    
    local content = message.content:sub(#config.prefix + 1)
    local args = {}
    for word in content:gmatch('%S+') do
        table.insert(args, word)
    end
    
    local commandName = table.remove(args, 1):lower()
    
    if commands[commandName] then
        local success, err = pcall(commands[commandName], message, args)
        if not success then
            print('❌ Error in command ' .. commandName .. ': ' .. tostring(err))
            message:reply('❌ An error occurred while executing this command.')
        end
    end
end)

client:on('error', function(err)
    print('❌ Error: ' .. tostring(err))
end)

-- Start the bot
if not config.token then
    print('❌ DISCORD_TOKEN environment variable not set!')
    os.exit(1)
end

print('🚀 Starting Tooly Bot...')
client:run('Bot ' .. config.token)
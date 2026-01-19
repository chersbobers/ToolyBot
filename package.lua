return {
  name = "tooly-bot",
  version = "1.0.0",
  description = "Discord bot written in Lua",
  tags = { "discord", "bot" },
  license = "MIT",
  author = { name = "Your Name" },
  homepage = "https://github.com/chersbobers/ToolyBot",
  dependencies = {
    "SinisterRectus/discordia@2.11.1",
    "luvit/secure-socket@1.2.3",
    "creationix/coro-http@3.2.3"
  },
  files = {
    "**.lua"
  }
}
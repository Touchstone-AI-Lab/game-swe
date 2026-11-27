local frames = 0
function love.draw()
    love.graphics.clear(0.06, 0.12, 0.16)
    love.graphics.setColor(0.4, 0.9, 0.7)
    love.graphics.print('Linux visible rendering probe - no Balatro game loaded', 40, 140)
    love.graphics.rectangle('fill', 40, 200, math.min(frames * 5, 600), 12)
    frames = frames + 1
    if frames == 120 then
        local renderer, version = love.graphics.getRendererInfo()
        local output = assert(io.open(assert(os.getenv('PROBE_RESULT')), 'w'))
        output:write('visible=', tostring(love.window.isVisible()), '\n',
            'frames=', frames, '\n', 'love=', love._version, '\n',
            'renderer=', renderer, '\n', 'renderer_version=', version, '\n',
            'save=', love.filesystem.getSaveDirectory(), '\n',
            'appdata=', love.filesystem.getAppdataDirectory(), '\n')
        output:close()
        love.event.quit(love.window.isVisible() and 0 or 2)
    end
end

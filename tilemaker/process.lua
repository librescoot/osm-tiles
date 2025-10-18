-- Custom Shortbread-based tile processing with maxspeed support
-- Optimized for LibreScoot/scootui navigation use case

-- Street types to include
local street_types = {
    motorway = true,
    trunk = true,
    primary = true,
    secondary = true,
    tertiary = true,
    unclassified = true,
    residential = true,
    living_street = true,
    service = true,
    pedestrian = true,
    track = true,
    path = true,
    footway = true,
    cycleway = true,
    steps = true,
    busway = true,
    taxiway = true
}

-- Water polygon types
local water_types = {
    water = true,
    pond = true,
    basin = true,
    reservoir = true,
    lake = true,
    river = true,
    stream = true,
    canal = true,
    drain = true,
    ditch = true
}

-- Helper function to check if a value exists in table
function has_value(tab, val)
    for k, v in pairs(tab) do
        if v == val then
            return true
        end
    end
    return false
end

-- Node function: not processing nodes for our use case
function node_function(node)
    -- We don't process individual nodes in this simplified schema
end

-- Way function: process roads and water features
function way_function()
    local highway = Find("highway")
    local waterway = Find("waterway")
    local natural = Find("natural")

    -- Process streets/roads
    if highway ~= "" and street_types[highway] then
        process_street(highway)
        -- Also create street label (only if street has a name or ref)
        local name = Find("name")
        local ref = Find("ref")
        if name ~= "" or ref ~= "" then
            process_street_label(highway, name, ref)
        end
        return
    end

    -- Process waterways as lines (not polygons)
    if waterway ~= "" and waterway ~= "riverbank" then
        process_water_line(waterway)
        return
    end
end

-- Area function: process water polygons and land
function area_function()
    local natural = Find("natural")
    local waterway = Find("waterway")
    local water = Find("water")
    local landuse = Find("landuse")
    local leisure = Find("leisure")

    -- Process water polygons
    if natural == "water" or water ~= "" or waterway == "riverbank" then
        process_water_polygon(natural, water)
        return
    end

    -- Process ALL land features - include any polygon with natural, landuse, or leisure tags
    -- This is more future-proof and includes everything scootui might need
    if natural ~= "" or landuse ~= "" or leisure ~= "" then
        process_land(natural, landuse, leisure)
        return
    end
end

-- Process street features
function process_street(highway)
    Layer("streets", false) -- false = linestring, not polygon
    Attribute("kind", highway)

    -- Extract name
    local name = Find("name")
    if name ~= "" then
        Attribute("name", name)
    end

    -- Extract reference (road number like "A7", "B27")
    local ref = Find("ref")
    if ref ~= "" then
        Attribute("ref", ref)
    end

    -- CRITICAL: Extract maxspeed (speed limit)
    local maxspeed = Find("maxspeed")
    if maxspeed ~= "" then
        Attribute("maxspeed", maxspeed)
    end

    -- Extract oneway information
    local oneway = Find("oneway")
    if oneway == "yes" then
        AttributeBoolean("oneway", true)
    elseif oneway == "-1" then
        AttributeBoolean("oneway_reverse", true)
    end

    -- Extract bridge/tunnel information
    local bridge = Find("bridge")
    if bridge == "yes" then
        AttributeBoolean("bridge", true)
    end

    local tunnel = Find("tunnel")
    if tunnel == "yes" then
        AttributeBoolean("tunnel", true)
    end

    -- Extract surface type
    local surface = Find("surface")
    if surface ~= "" then
        Attribute("surface", surface)
    end

    -- Extract lanes if available
    local lanes = Find("lanes")
    if lanes ~= "" then
        Attribute("lanes", lanes)
    end

    -- Set minimum zoom based on road type
    if highway == "motorway" or highway == "trunk" then
        MinZoom(10)
    elseif highway == "primary" then
        MinZoom(11)
    elseif highway == "secondary" then
        MinZoom(12)
    elseif highway == "tertiary" then
        MinZoom(13)
    else
        MinZoom(14)
    end
end

-- Process water polygon features
function process_water_polygon(natural, water)
    Layer("water_polygons", true) -- true = polygon

    -- Set kind based on water type
    if water ~= "" then
        Attribute("kind", water)
    elseif natural == "water" then
        Attribute("kind", "water")
    else
        Attribute("kind", "water")
    end

    -- Extract name if available
    local name = Find("name")
    if name ~= "" then
        Attribute("name", name)
    end

    -- Set zoom levels based on size
    -- Larger water bodies appear at lower zoom levels
    local area = Area()
    if area > 1000000 then -- Very large (lakes, reservoirs)
        MinZoom(6)
    elseif area > 100000 then -- Large
        MinZoom(8)
    elseif area > 10000 then -- Medium
        MinZoom(10)
    else -- Small
        MinZoom(12)
    end
end

-- Process water line features (rivers, streams, canals, etc.)
function process_water_line(waterway)
    Layer("water_lines", false) -- false = linestring

    -- Set kind based on waterway type
    Attribute("kind", waterway)

    -- Extract name if available
    local name = Find("name")
    if name ~= "" then
        Attribute("name", name)
    end

    -- Set zoom levels based on waterway type
    if waterway == "river" then
        MinZoom(8)
    elseif waterway == "canal" then
        MinZoom(10)
    elseif waterway == "stream" then
        MinZoom(12)
    else -- drain, ditch, etc.
        MinZoom(13)
    end
end

-- Process land features (base layer for map rendering)
function process_land(natural, landuse, leisure)
    Layer("land", true) -- true = polygon

    -- Determine kind - prioritize leisure (parks), then natural, then landuse
    local kind
    if leisure ~= "" then
        kind = leisure
    elseif natural ~= "" then
        kind = natural
    elseif landuse ~= "" then
        kind = landuse
    else
        kind = "unknown"
    end

    Attribute("kind", kind)

    -- Set minimum zoom
    -- Land features are generally visible at all zooms
    MinZoom(0)
end

-- Process street label (point feature for labeling roads on map)
function process_street_label(highway, name, ref)
    LayerAsCentroid("street_labels") -- Create point feature at centroid of linestring
    Attribute("kind", highway)

    if name ~= "" then
        Attribute("name", name)
    end

    if ref ~= "" then
        Attribute("ref", ref)
    end

    -- Set minimum zoom based on road type (same as streets)
    if highway == "motorway" or highway == "trunk" then
        MinZoom(10)
    elseif highway == "primary" then
        MinZoom(11)
    elseif highway == "secondary" then
        MinZoom(12)
    elseif highway == "tertiary" then
        MinZoom(13)
    else
        MinZoom(14)
    end
end

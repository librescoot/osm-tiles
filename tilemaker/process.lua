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
function way_function(way)
    local highway = way:Find("highway")
    local waterway = way:Find("waterway")
    local natural = way:Find("natural")

    -- Process streets/roads
    if highway ~= "" and street_types[highway] then
        process_street(way, highway)
        return
    end

    -- Process waterways as lines (not polygons)
    -- Polygonal water features handled in area_function
end

-- Area function: process water polygons and land
function area_function(way)
    local natural = way:Find("natural")
    local waterway = way:Find("waterway")
    local water = way:Find("water")
    local landuse = way:Find("landuse")

    -- Process water polygons
    if natural == "water" or water ~= "" or waterway == "riverbank" then
        process_water_polygon(way, natural, water)
        return
    end

    -- Process land (everything else that forms the base layer)
    if natural == "wood" or natural == "grassland" or natural == "scrub" or
       landuse == "forest" or landuse == "grass" or landuse == "meadow" or
       landuse == "farmland" or landuse == "residential" or landuse == "commercial" then
        process_land(way, natural, landuse)
        return
    end
end

-- Process street features
function process_street(way, highway)
    way:Layer("streets", false) -- false = linestring, not polygon
    way:Attribute("kind", highway)

    -- Extract name
    local name = way:Find("name")
    if name ~= "" then
        way:Attribute("name", name)
    end

    -- Extract reference (road number like "A7", "B27")
    local ref = way:Find("ref")
    if ref ~= "" then
        way:Attribute("ref", ref)
    end

    -- CRITICAL: Extract maxspeed (speed limit)
    local maxspeed = way:Find("maxspeed")
    if maxspeed ~= "" then
        way:Attribute("maxspeed", maxspeed)
    end

    -- Extract oneway information
    local oneway = way:Find("oneway")
    if oneway == "yes" then
        way:AttributeBoolean("oneway", true)
    elseif oneway == "-1" then
        way:AttributeBoolean("oneway_reverse", true)
    end

    -- Extract bridge/tunnel information
    local bridge = way:Find("bridge")
    if bridge == "yes" then
        way:AttributeBoolean("bridge", true)
    end

    local tunnel = way:Find("tunnel")
    if tunnel == "yes" then
        way:AttributeBoolean("tunnel", true)
    end

    -- Extract surface type
    local surface = way:Find("surface")
    if surface ~= "" then
        way:Attribute("surface", surface)
    end

    -- Extract lanes if available
    local lanes = way:Find("lanes")
    if lanes ~= "" then
        way:Attribute("lanes", lanes)
    end

    -- Set minimum zoom based on road type
    if highway == "motorway" or highway == "trunk" then
        way:MinZoom(10)
    elseif highway == "primary" then
        way:MinZoom(11)
    elseif highway == "secondary" then
        way:MinZoom(12)
    elseif highway == "tertiary" then
        way:MinZoom(13)
    else
        way:MinZoom(14)
    end
end

-- Process water polygon features
function process_water_polygon(way, natural, water)
    way:Layer("water_polygons", true) -- true = polygon

    -- Set kind based on water type
    if water ~= "" then
        way:Attribute("kind", water)
    elseif natural == "water" then
        way:Attribute("kind", "water")
    else
        way:Attribute("kind", "water")
    end

    -- Extract name if available
    local name = way:Find("name")
    if name ~= "" then
        way:Attribute("name", name)
    end

    -- Set zoom levels based on size
    -- Larger water bodies appear at lower zoom levels
    local area = way:Area()
    if area > 1000000 then -- Very large (lakes, reservoirs)
        way:MinZoom(6)
    elseif area > 100000 then -- Large
        way:MinZoom(8)
    elseif area > 10000 then -- Medium
        way:MinZoom(10)
    else -- Small
        way:MinZoom(12)
    end
end

-- Process land features (base layer for map rendering)
function process_land(way, natural, landuse)
    way:Layer("land", true) -- true = polygon

    -- Determine kind
    local kind
    if natural ~= "" then
        kind = natural
    elseif landuse ~= "" then
        kind = landuse
    else
        kind = "unknown"
    end

    way:Attribute("kind", kind)

    -- Set minimum zoom
    -- Land features are generally visible at all zooms
    way:MinZoom(0)
end

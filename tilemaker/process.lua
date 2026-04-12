-- Custom Shortbread-based tile processing
-- Includes streets with speed limits, addresses, and 3D buildings
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

-- Helper function to check if node has address tags
function has_address_tags()
    local housenumber = Find("addr:housenumber")
    local street = Find("addr:street")
    return housenumber ~= "" or street ~= ""
end

-- Node function: process address nodes
function node_function(node)
    if has_address_tags() then
        process_address_point()
    end
end

-- Way function: process roads, water features, and buildings
function way_function()
    local highway = Find("highway")
    local waterway = Find("waterway")

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

    -- Process buildings (most buildings are closed ways)
    if IsClosed() then
        local building = Find("building")
        if building ~= "" and building ~= "no" then
            process_building(building)
            -- Also extract address from building if available
            if has_address_tags() then
                process_address_point()
            end
            return
        end
    end
end

-- Area function: process water polygons, land, and multipolygon buildings
function area_function()
    local natural = Find("natural")
    local waterway = Find("waterway")
    local water = Find("water")
    local landuse = Find("landuse")
    local leisure = Find("leisure")

    -- Process buildings (multipolygon relations)
    local building = Find("building")
    if building ~= "" and building ~= "no" then
        process_building(building)
        if has_address_tags() then
            process_address_point()
        end
        return
    end

    -- Process water polygons
    if natural == "water" or water ~= "" or waterway == "riverbank" then
        process_water_polygon(natural, water)
        return
    end

    -- Process ALL land features
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

-- Process address points (from nodes or building centroids)
function process_address_point()
    LayerAsCentroid("addresses")

    local housenumber = Find("addr:housenumber")
    if housenumber ~= "" then
        Attribute("housenumber", housenumber)
    end

    local street = Find("addr:street")
    if street ~= "" then
        Attribute("street", street)
    end

    local city = Find("addr:city")
    if city ~= "" then
        Attribute("city", city)
    end

    local postcode = Find("addr:postcode")
    if postcode ~= "" then
        Attribute("postcode", postcode)
    end

    local suburb = Find("addr:suburb")
    if suburb ~= "" then
        Attribute("suburb", suburb)
    end

    local place_name = Find("name")
    if place_name ~= "" then
        Attribute("name", place_name)
    end

    MinZoom(14)
end

-- Process building features
function process_building(building)
    Layer("buildings", true) -- true = polygon (matches Shortbread/Versatiles convention)

    Attribute("kind", building)

    -- Extract height: prefer building:height, then height, then estimate from levels
    local height = Find("building:height")
    if height == "" then height = Find("height") end
    local levels = Find("building:levels")
    local min_height = Find("building:min_height")
    if min_height == "" then min_height = Find("min_height") end
    local min_levels = Find("building:min_level")

    -- Calculate render_height (meters)
    local render_height = 10 -- default fallback
    if height ~= "" then
        local h = tonumber(height)
        if h then render_height = h end
    elseif levels ~= "" then
        local l = tonumber(levels)
        if l then render_height = l * 3 end
    end

    -- Calculate render_min_height (for floating parts like skyways)
    local render_min_height = 0
    if min_height ~= "" then
        local mh = tonumber(min_height)
        if mh then render_min_height = mh end
    elseif min_levels ~= "" then
        local ml = tonumber(min_levels)
        if ml then render_min_height = ml * 3 end
    end

    AttributeNumeric("render_height", render_height)
    AttributeNumeric("render_min_height", render_min_height)

    MinZoom(13)
end

-- Process water polygon features
function process_water_polygon(natural, water)
    Layer("water_polygons", true) -- true = polygon

    if water ~= "" then
        Attribute("kind", water)
    elseif natural == "water" then
        Attribute("kind", "water")
    else
        Attribute("kind", "water")
    end

    local name = Find("name")
    if name ~= "" then
        Attribute("name", name)
    end

    local area = Area()
    if area > 1000000 then
        MinZoom(6)
    elseif area > 100000 then
        MinZoom(8)
    elseif area > 10000 then
        MinZoom(10)
    else
        MinZoom(12)
    end
end

-- Process water line features (rivers, streams, canals, etc.)
function process_water_line(waterway)
    Layer("water_lines", false) -- false = linestring

    Attribute("kind", waterway)

    local name = Find("name")
    if name ~= "" then
        Attribute("name", name)
    end

    if waterway == "river" then
        MinZoom(8)
    elseif waterway == "canal" then
        MinZoom(10)
    elseif waterway == "stream" then
        MinZoom(12)
    else
        MinZoom(13)
    end
end

-- Process land features (base layer for map rendering)
function process_land(natural, landuse, leisure)
    Layer("land", true) -- true = polygon

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
    MinZoom(0)
end

-- Process street label (point feature for labeling roads on map)
function process_street_label(highway, name, ref)
    LayerAsCentroid("street_labels")
    Attribute("kind", highway)

    if name ~= "" then
        Attribute("name", name)
    end

    if ref ~= "" then
        Attribute("ref", ref)
    end

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

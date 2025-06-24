package main

import (
	"bytes"
	"compress/gzip"
	"database/sql"
	"flag"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"slices"
	"strings"

	"github.com/librescoot/osm-tiles/protos"

	_ "github.com/mattn/go-sqlite3"
	"google.golang.org/protobuf/proto"
)

func NewTilesProcessor(dbPath string) (*TilesProcessor, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, err
	}

	return &TilesProcessor{dbPath: dbPath, db: db}, nil
}

type TilesProcessor struct {
	dbPath string
	db     *sql.DB
}

func (tp *TilesProcessor) Close() error {
	if tp.db != nil {
		_, err := tp.db.Exec("VACUUM")
		if err != nil {
			return fmt.Errorf("vacuum database: %w", err)
		}

		err = tp.db.Close()
		if err != nil {
			return fmt.Errorf("close database: %w", err)
		}

		// reopen database to disabble WAL mode
		db, err := sql.Open("sqlite3", tp.dbPath)
		if err != nil {
			return fmt.Errorf("reopen database: %w", err)
		}

		// disable journal, not required for reading
		_, err = db.Exec("PRAGMA journal_mode=OFF")
		if err != nil {
			return fmt.Errorf("disable journal mode: %w", err)
		}

		return db.Close()
	}

	return nil
}

func (tp *TilesProcessor) decodeTile(data []byte) (*protos.Tile, error) {
	gzipReader, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return nil, fmt.Errorf("create gzip reader: %w", err)
	}
	defer gzipReader.Close()

	protoData, err := io.ReadAll(gzipReader)
	if err != nil {
		return nil, fmt.Errorf("read gzip data: %w", err)
	}

	var tileProto protos.Tile
	err = proto.Unmarshal(protoData, &tileProto)
	if err != nil {
		return nil, fmt.Errorf("unmarshal tile data: %w", err)
	}

	return &tileProto, nil
}

func (tp *TilesProcessor) encodeTile(tileProto *protos.Tile) ([]byte, error) {
	protoData, err := proto.Marshal(tileProto)
	if err != nil {
		return nil, fmt.Errorf("marshal tile data: %w", err)
	}

	var compressedData bytes.Buffer
	gzipWriter := gzip.NewWriter(&compressedData)
	_, err = gzipWriter.Write(protoData)
	if err != nil {
		return nil, fmt.Errorf("compress tile data: %w", err)
	}
	gzipWriter.Close()

	return compressedData.Bytes(), nil
}

func (tp *TilesProcessor) listAvailableLayers(db *sql.DB) ([]string, error) {
	rows, err := db.Query("SELECT tile_data FROM tiles")
	if err != nil {
		return nil, fmt.Errorf("query tiles: %w", err)
	}
	defer rows.Close()

	layers := make(map[string]struct{})

	for rows.Next() {
		var tileData []byte
		err = rows.Scan(&tileData)
		if err != nil {
			return nil, fmt.Errorf("scan tile data: %w", err)
		}

		gzipReader, err := gzip.NewReader(bytes.NewReader(tileData))
		if err != nil {
			return nil, fmt.Errorf("create gzip reader: %w", err)
		}

		protoData, err := io.ReadAll(gzipReader)
		if err != nil {
			return nil, fmt.Errorf("read gzip data: %w", err)
		}
		gzipReader.Close()

		var tileProto protos.Tile
		err = proto.Unmarshal(protoData, &tileProto)
		if err != nil {
			return nil, fmt.Errorf("unmarshal tile data: %w", err)
		}

		// Add all layer names to our map
		for _, layer := range tileProto.Layers {
			layers[layer.GetName()] = struct{}{}
		}
	}

	var keys []string
	for layer := range layers {
		keys = append(keys, layer)
	}

	slices.Sort(keys)

	return keys, nil
}

type TileTransformer func(x, y, z int, t *protos.Tile_Layer) (drop, modified bool)

func (tp *TilesProcessor) removeLayers(layersToRemove []string) TileTransformer {
	layersMap := make(map[string]bool)
	for _, layer := range layersToRemove {
		layersMap[layer] = true
	}

	return func(x, y, z int, l *protos.Tile_Layer) (drop, modified bool) {
		return layersMap[l.GetName()], false
	}
}

func (tp *TilesProcessor) removeStreets(streetsToKeep []string) TileTransformer {
	streetsMap := make(map[string]bool)
	for _, street := range streetsToKeep {
		streetsMap[street] = true
	}

	return func(x, y, z int, l *protos.Tile_Layer) (drop, modified bool) {
		if l.GetName() != "streets" {
			return
		}

		var filteredFeatures []*protos.Tile_Feature
	features:
		for _, feature := range l.GetFeatures() {
			tags := feature.GetTags()
			for i := 0; i < len(tags); i += 2 {
				if i+1 < len(tags) {
					keyIndex := tags[i]
					valueIndex := tags[i+1]

					if keyIndex < uint32(len(l.Keys)) && valueIndex < uint32(len(l.Values)) {
						key := l.Keys[keyIndex]
						value := l.Values[valueIndex]

						if key == "kind" && !streetsMap[value.GetStringValue()] {
							continue features
						}
					}
				}
			}
			filteredFeatures = append(filteredFeatures, feature)
		}

		drop = len(filteredFeatures) == 0                   // no features left
		modified = len(l.Features) != len(filteredFeatures) // some features were removed

		l.Features = filteredFeatures
		return
	}
}

func (tp *TilesProcessor) buildAddressIndex(addresses map[int64]*Address) TileTransformer {
	var currentAddressID int64 = 1

	return func(tileX, tileY, tileZ int, l *protos.Tile_Layer) (drop, modified bool) {
		if l.GetName() != "addresses" {
			return false, false // Corrected: return default values
		}

		features := l.GetFeatures()
		extent := l.GetExtent() // uint32, ensure float64 conversion for division

		for _, feature := range features {
			if feature.GetType() != protos.Tile_POINT {
				continue // This transformer only processes POINT features in the "addresses" layer
			}

			geom := feature.GetGeometry()
			if len(geom) == 0 {
				// Optionally log an empty geometry warning
				continue
			}

			commandInteger := geom[0]
			commandID := commandInteger & 0x7
			commandCount := commandInteger >> 3

			if commandID != 1 { // For POINT geometries, the command MUST be MoveTo (ID 1)
				// Optionally log a warning for invalid command
				continue
			}

			// Expected geometry length: 1 (CommandInteger) + commandCount * 2 (Parameters)
			if uint32(len(geom)) != (1 + commandCount*2) {
				// Optionally log a warning for malformed geometry
				continue
			}

			currentCursorX := int32(0) // Cursor X relative to tile origin (0,0)
			currentCursorY := int32(0) // Cursor Y relative to tile origin (0,0)
			paramIdx := 1              // Parameters start at geom[1]

			for i := uint32(0); i < commandCount; i++ {
				// These checks ensure we don't go out of bounds, though the initial length check should cover this.
				if paramIdx >= len(geom) || paramIdx+1 >= len(geom) {
					// Optionally log error: geometry too short for parameters
					break // Stop processing this feature
				}

				dX := decodeZigZag(geom[paramIdx])
				paramIdx++
				dY := decodeZigZag(geom[paramIdx])
				paramIdx++

				currentCursorX += dX // Update cursor to absolute tile coordinates
				currentCursorY += dY

				x := float64(currentCursorX)
				y := float64(currentCursorY)

				// Convert from tile coordinates to geographic coordinates
				n := math.Pow(2.0, float64(tileZ)) // Use actual zoom level tileZ

				lon := (float64(tileX)+x/float64(extent))/n*360.0 - 180.0
				y_normalized := 1.0 - (float64(tileY)+y/float64(extent))/n // Normalized Y for Web Mercator, flipped for TMS

				z_calc := math.Pi * (1.0 - 2.0*y_normalized)
				latRad := math.Atan((math.Exp(z_calc) - math.Exp(-z_calc)) / 2.0)
				lat := latRad * 180.0 / math.Pi

				id := currentAddressID
				currentAddressID++

				addresses[id] = &Address{
					ID:          id,
					Coordinates: LatLng{Lat: lat, Lng: lon},
					X:           x,
					Y:           y,
				}
			}
		}
		return false, false // Finished processing "addresses" layer, no modifications to the layer itself
	}
}

// decodeZigZag decodes a zigzag-encoded value
func decodeZigZag(n uint32) int32 {
	return int32((n >> 1) ^ (-(n & 1)))
}

// toBase32 converts an integer to a base32 string
func toBase32(id int64) string {
	const alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
	result := ""

	if id == 0 {
		return "0"
	}

	for id > 0 {
		result = string(alphabet[id%32]) + result
		id /= 32
	}

	return result
}

// Address represents a geographic address with coordinates
type Address struct {
	ID          int64
	Code        string
	Coordinates LatLng
	X           float64
	Y           float64
}

// LatLng represents a geographic coordinate
type LatLng struct {
	Lat float64
	Lng float64
}

func (tp *TilesProcessor) transform(transformers ...TileTransformer) error {
	// Enable WAL mode
	_, err := tp.db.Exec("PRAGMA journal_mode=WAL")
	if err != nil {
		return fmt.Errorf("enable WAL mode: %w", err)
	}

	// Get all tiles
	rows, err := tp.db.Query("SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles")
	if err != nil {
		return fmt.Errorf("query tiles: %w", err)
	}
	defer rows.Close()

	tx, err := tp.db.Begin()
	if err != nil {
		return fmt.Errorf("begin transaction: %w", err)
	}

	// Prepare update statement
	updateStmt, err := tx.Prepare("UPDATE tiles SET tile_data = ? WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?")
	if err != nil {
		return fmt.Errorf("prepare update statement: %w", err)
	}
	defer updateStmt.Close()

	for rows.Next() {
		var zoom, column, row int
		var tileData []byte
		err = rows.Scan(&zoom, &column, &row, &tileData)
		if err != nil {
			log.Fatal(err)
		}

		tileProto, err := tp.decodeTile(tileData)
		if err != nil {
			return fmt.Errorf("decode tile: %w", err)
		}

		var anyModified bool
		var filteredLayers []*protos.Tile_Layer
	layer:
		for _, layer := range tileProto.Layers {
			for _, transformer := range transformers {
				drop, modified := transformer(column, row, zoom, layer)
				if drop {
					// Skip this layer if it should be dropped
					continue layer
				}

				anyModified = anyModified || modified
				filteredLayers = append(filteredLayers, layer)
			}
		}

		// If no layers were removed or modified, skip update
		if len(filteredLayers) == len(tileProto.Layers) && !anyModified {
			continue
		}

		// Update tile with filtered layers
		tileProto.Layers = filteredLayers
		compressedData, err := tp.encodeTile(tileProto)
		if err != nil {
			return fmt.Errorf("encode tile: %w", err)
		}

		// Update tile in database
		_, err = updateStmt.Exec(compressedData, zoom, column, row)
		if err != nil {
			return fmt.Errorf("update tile data: %w", err)
		}
	}

	return tx.Commit()
}

const addressesTableSchema = `
CREATE TABLE IF NOT EXISTS addresses (
	id TEXT PRIMARY KEY,
	lat REAL NOT NULL,
	lng REAL NOT NULL
);
`

func (tp *TilesProcessor) writeAddresses(addresses map[int64]*Address) error {
	// find highest address ID
	var maxID int64 = 0
	for id := range addresses {
		if id > maxID {
			maxID = id
		}
	}

	// based on the max ID, calculate how many digits we need for base32 encoding
	base32Digits := int(math.Ceil(math.Log2(float64(maxID+1)) / math.Log2(32)))
	// create a new map with base32 encoded IDs, using padding to make sure all codes have the same length
	for id, address := range addresses {
		address.Code = toBase32(id)
		if len(address.Code) < base32Digits {
			address.Code = strings.Repeat("0", base32Digits-len(address.Code)) + address.Code
		}
		addresses[id] = address
	}

	_, err := tp.db.Exec(addressesTableSchema)
	if err != nil {
		return fmt.Errorf("create addresses table: %w", err)
	}

	tx, err := tp.db.Begin()
	if err != nil {
		return fmt.Errorf("begin transaction: %w", err)
	}

	stmt, err := tx.Prepare("INSERT OR REPLACE INTO addresses (id, lat, lng) VALUES (?, ?, ?)")
	if err != nil {
		return fmt.Errorf("prepare insert statement: %w", err)
	}
	defer stmt.Close()

	for _, address := range addresses {
		_, err := stmt.Exec(address.Code, address.Coordinates.Lat, address.Coordinates.Lng)
		if err != nil {
			return fmt.Errorf("insert address %s: %w", address.ID, err)
		}
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("commit transaction: %w", err)
	}

	return nil
}

// on Windows, os.Rename does not work across different drives, so we're copying the file instead
func moveFile(src, dst string) error {
	srcFile, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("open source file: %w", err)
	}
	defer srcFile.Close()

	err = os.MkdirAll(filepath.Dir(dst), 0755)
	if err != nil {
		return fmt.Errorf("create destination directory: %w", err)
	}

	dstFile, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf("create destination file: %w", err)
	}
	defer dstFile.Close()

	_, err = io.Copy(dstFile, srcFile)
	if err != nil {
		return fmt.Errorf("copy file: %w", err)
	}

	err = dstFile.Close()
	if err != nil {
		return fmt.Errorf("close destination file: %w", err)
	}

	if srcFile.Close() == nil {
		if os.Remove(src) != nil {
			log.Printf("Warning: failed to remove source file %s: %v", src, err)
		}
	}

	return nil
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)

	// Parse command line flags
	listLayers := flag.Bool("list", false, "List all available layers")
	removeLayers := flag.String("remove", "", "Comma-separated list of layers to remove")
	streetsToKeep := flag.String("streets", "", "Comma-separated list of street kinds to keep")
	source := flag.String("source", "", "Source file")
	out := flag.String("out", "", "Output file (default: same as input)")
	flag.Parse()

	// download database file
	if *source == "" {
		log.Fatal("Please provide the url to the MBTiles file")
	}

	tmpFile, err := os.CreateTemp("", "tiles-*.mbtiles")
	if err != nil {
		log.Fatalf("Failed to create temporary file: %v", err)
	}

	log.Printf("Downloading tiles to: %s", tmpFile.Name())
	response, err := http.Get(*source)
	if err != nil {
		log.Fatalf("Failed to download MBTiles file: %v", err)
	}

	defer response.Body.Close()
	_, err = io.Copy(tmpFile, response.Body)
	if err != nil {
		log.Fatalf("Failed to write MBTiles file: %v", err)
	}

	err = tmpFile.Close()
	if err != nil {
		log.Fatalf("Failed to close temporary file: %v", err)
	}

	tp, err := NewTilesProcessor(tmpFile.Name())
	if err != nil {
		log.Fatalf("Failed to open MBTiles file: %v", err)
	}

	if *listLayers {
		layers, err := tp.listAvailableLayers(tp.db)
		if err != nil {
			log.Fatalf("Failed to list layers: %v", err)
		}

		fmt.Println("Available layers:")
		for _, layer := range layers {
			fmt.Println("-", layer)
		}
		return
	}

	var transformers []TileTransformer
	var addresses = make(map[int64]*Address)
	transformers = append(transformers, tp.buildAddressIndex(addresses))

	if *removeLayers != "" {
		layersToRemove := strings.Split(*removeLayers, ",")
		transformers = append(transformers, tp.removeLayers(layersToRemove))
	}

	if *streetsToKeep != "" {
		streetsToKeepList := strings.Split(*streetsToKeep, ",")
		transformers = append(transformers, tp.removeStreets(streetsToKeepList))
	}

	if len(transformers) == 0 {
		log.Fatal("No transformations specified. Use -list to see available layers or -remove to specify layers to remove.")
	}

	log.Println("Processing tiles")
	err = tp.transform(transformers...)
	if err != nil {
		log.Fatalf("Failed to transform tiles: %v", err)
	}

	if len(addresses) > 0 {
		err = tp.writeAddresses(addresses)
		if err != nil {
			log.Fatalf("Failed to write addresses: %v", err)
		}
	}

	err = tp.Close()
	if err != nil {
		log.Fatalf("Failed to close tiles processor: %v", err)
	}

	if *out != "" {
		log.Printf("Moving temporary file to output: %s", *out)
		err = moveFile(tmpFile.Name(), *out)
		if err != nil {
			log.Fatalf("Failed to rename output file: %v", err)
		}
	} else {
		fmt.Println("Output file not specified, keeping temporary file:", tmpFile.Name())
	}
}

// pier_lines,pois,dam_lines,boundary_labels,sites,buildings,public_transport,water_lines_labels,ocean,water_lines,water_polygons,place_labels,aerialways,ferries,pier_polygons,land

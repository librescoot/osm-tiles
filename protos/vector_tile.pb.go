// Code generated by protoc-gen-go. DO NOT EDIT.
// versions:
// 	protoc-gen-go v1.36.6
// 	protoc        v5.29.3
// source: vector_tile.proto

package protos

import (
	protoreflect "google.golang.org/protobuf/reflect/protoreflect"
	protoimpl "google.golang.org/protobuf/runtime/protoimpl"
	reflect "reflect"
	sync "sync"
	unsafe "unsafe"
)

const (
	// Verify that this generated code is sufficiently up-to-date.
	_ = protoimpl.EnforceVersion(20 - protoimpl.MinVersion)
	// Verify that runtime/protoimpl is sufficiently up-to-date.
	_ = protoimpl.EnforceVersion(protoimpl.MaxVersion - 20)
)

// GeomType is described in section 4.3.4 of the specification
type Tile_GeomType int32

const (
	Tile_UNKNOWN    Tile_GeomType = 0
	Tile_POINT      Tile_GeomType = 1
	Tile_LINESTRING Tile_GeomType = 2
	Tile_POLYGON    Tile_GeomType = 3
)

// Enum value maps for Tile_GeomType.
var (
	Tile_GeomType_name = map[int32]string{
		0: "UNKNOWN",
		1: "POINT",
		2: "LINESTRING",
		3: "POLYGON",
	}
	Tile_GeomType_value = map[string]int32{
		"UNKNOWN":    0,
		"POINT":      1,
		"LINESTRING": 2,
		"POLYGON":    3,
	}
)

func (x Tile_GeomType) Enum() *Tile_GeomType {
	p := new(Tile_GeomType)
	*p = x
	return p
}

func (x Tile_GeomType) String() string {
	return protoimpl.X.EnumStringOf(x.Descriptor(), protoreflect.EnumNumber(x))
}

func (Tile_GeomType) Descriptor() protoreflect.EnumDescriptor {
	return file_vector_tile_proto_enumTypes[0].Descriptor()
}

func (Tile_GeomType) Type() protoreflect.EnumType {
	return &file_vector_tile_proto_enumTypes[0]
}

func (x Tile_GeomType) Number() protoreflect.EnumNumber {
	return protoreflect.EnumNumber(x)
}

// Deprecated: Do not use.
func (x *Tile_GeomType) UnmarshalJSON(b []byte) error {
	num, err := protoimpl.X.UnmarshalJSONEnum(x.Descriptor(), b)
	if err != nil {
		return err
	}
	*x = Tile_GeomType(num)
	return nil
}

// Deprecated: Use Tile_GeomType.Descriptor instead.
func (Tile_GeomType) EnumDescriptor() ([]byte, []int) {
	return file_vector_tile_proto_rawDescGZIP(), []int{0, 0}
}

type Tile struct {
	state           protoimpl.MessageState `protogen:"open.v1"`
	Layers          []*Tile_Layer          `protobuf:"bytes,3,rep,name=layers" json:"layers,omitempty"`
	extensionFields protoimpl.ExtensionFields
	unknownFields   protoimpl.UnknownFields
	sizeCache       protoimpl.SizeCache
}

func (x *Tile) Reset() {
	*x = Tile{}
	mi := &file_vector_tile_proto_msgTypes[0]
	ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
	ms.StoreMessageInfo(mi)
}

func (x *Tile) String() string {
	return protoimpl.X.MessageStringOf(x)
}

func (*Tile) ProtoMessage() {}

func (x *Tile) ProtoReflect() protoreflect.Message {
	mi := &file_vector_tile_proto_msgTypes[0]
	if x != nil {
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		if ms.LoadMessageInfo() == nil {
			ms.StoreMessageInfo(mi)
		}
		return ms
	}
	return mi.MessageOf(x)
}

// Deprecated: Use Tile.ProtoReflect.Descriptor instead.
func (*Tile) Descriptor() ([]byte, []int) {
	return file_vector_tile_proto_rawDescGZIP(), []int{0}
}

func (x *Tile) GetLayers() []*Tile_Layer {
	if x != nil {
		return x.Layers
	}
	return nil
}

// Variant type encoding
// The use of values is described in section 4.1 of the specification
type Tile_Value struct {
	state protoimpl.MessageState `protogen:"open.v1"`
	// Exactly one of these values must be present in a valid message
	StringValue     *string  `protobuf:"bytes,1,opt,name=string_value,json=stringValue" json:"string_value,omitempty"`
	FloatValue      *float32 `protobuf:"fixed32,2,opt,name=float_value,json=floatValue" json:"float_value,omitempty"`
	DoubleValue     *float64 `protobuf:"fixed64,3,opt,name=double_value,json=doubleValue" json:"double_value,omitempty"`
	IntValue        *int64   `protobuf:"varint,4,opt,name=int_value,json=intValue" json:"int_value,omitempty"`
	UintValue       *uint64  `protobuf:"varint,5,opt,name=uint_value,json=uintValue" json:"uint_value,omitempty"`
	SintValue       *int64   `protobuf:"zigzag64,6,opt,name=sint_value,json=sintValue" json:"sint_value,omitempty"`
	BoolValue       *bool    `protobuf:"varint,7,opt,name=bool_value,json=boolValue" json:"bool_value,omitempty"`
	extensionFields protoimpl.ExtensionFields
	unknownFields   protoimpl.UnknownFields
	sizeCache       protoimpl.SizeCache
}

func (x *Tile_Value) Reset() {
	*x = Tile_Value{}
	mi := &file_vector_tile_proto_msgTypes[1]
	ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
	ms.StoreMessageInfo(mi)
}

func (x *Tile_Value) String() string {
	return protoimpl.X.MessageStringOf(x)
}

func (*Tile_Value) ProtoMessage() {}

func (x *Tile_Value) ProtoReflect() protoreflect.Message {
	mi := &file_vector_tile_proto_msgTypes[1]
	if x != nil {
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		if ms.LoadMessageInfo() == nil {
			ms.StoreMessageInfo(mi)
		}
		return ms
	}
	return mi.MessageOf(x)
}

// Deprecated: Use Tile_Value.ProtoReflect.Descriptor instead.
func (*Tile_Value) Descriptor() ([]byte, []int) {
	return file_vector_tile_proto_rawDescGZIP(), []int{0, 0}
}

func (x *Tile_Value) GetStringValue() string {
	if x != nil && x.StringValue != nil {
		return *x.StringValue
	}
	return ""
}

func (x *Tile_Value) GetFloatValue() float32 {
	if x != nil && x.FloatValue != nil {
		return *x.FloatValue
	}
	return 0
}

func (x *Tile_Value) GetDoubleValue() float64 {
	if x != nil && x.DoubleValue != nil {
		return *x.DoubleValue
	}
	return 0
}

func (x *Tile_Value) GetIntValue() int64 {
	if x != nil && x.IntValue != nil {
		return *x.IntValue
	}
	return 0
}

func (x *Tile_Value) GetUintValue() uint64 {
	if x != nil && x.UintValue != nil {
		return *x.UintValue
	}
	return 0
}

func (x *Tile_Value) GetSintValue() int64 {
	if x != nil && x.SintValue != nil {
		return *x.SintValue
	}
	return 0
}

func (x *Tile_Value) GetBoolValue() bool {
	if x != nil && x.BoolValue != nil {
		return *x.BoolValue
	}
	return false
}

// Features are described in section 4.2 of the specification
type Tile_Feature struct {
	state protoimpl.MessageState `protogen:"open.v1"`
	Id    *uint64                `protobuf:"varint,1,opt,name=id,def=0" json:"id,omitempty"`
	// Tags of this feature are encoded as repeated pairs of
	// integers.
	// A detailed description of tags is located in sections
	// 4.2 and 4.4 of the specification
	Tags []uint32 `protobuf:"varint,2,rep,packed,name=tags" json:"tags,omitempty"`
	// The type of geometry stored in this feature.
	Type *Tile_GeomType `protobuf:"varint,3,opt,name=type,enum=protos.Tile_GeomType,def=0" json:"type,omitempty"`
	// Contains a stream of commands and parameters (vertices).
	// A detailed description on geometry encoding is located in
	// section 4.3 of the specification.
	Geometry      []uint32 `protobuf:"varint,4,rep,packed,name=geometry" json:"geometry,omitempty"`
	unknownFields protoimpl.UnknownFields
	sizeCache     protoimpl.SizeCache
}

// Default values for Tile_Feature fields.
const (
	Default_Tile_Feature_Id   = uint64(0)
	Default_Tile_Feature_Type = Tile_UNKNOWN
)

func (x *Tile_Feature) Reset() {
	*x = Tile_Feature{}
	mi := &file_vector_tile_proto_msgTypes[2]
	ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
	ms.StoreMessageInfo(mi)
}

func (x *Tile_Feature) String() string {
	return protoimpl.X.MessageStringOf(x)
}

func (*Tile_Feature) ProtoMessage() {}

func (x *Tile_Feature) ProtoReflect() protoreflect.Message {
	mi := &file_vector_tile_proto_msgTypes[2]
	if x != nil {
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		if ms.LoadMessageInfo() == nil {
			ms.StoreMessageInfo(mi)
		}
		return ms
	}
	return mi.MessageOf(x)
}

// Deprecated: Use Tile_Feature.ProtoReflect.Descriptor instead.
func (*Tile_Feature) Descriptor() ([]byte, []int) {
	return file_vector_tile_proto_rawDescGZIP(), []int{0, 1}
}

func (x *Tile_Feature) GetId() uint64 {
	if x != nil && x.Id != nil {
		return *x.Id
	}
	return Default_Tile_Feature_Id
}

func (x *Tile_Feature) GetTags() []uint32 {
	if x != nil {
		return x.Tags
	}
	return nil
}

func (x *Tile_Feature) GetType() Tile_GeomType {
	if x != nil && x.Type != nil {
		return *x.Type
	}
	return Default_Tile_Feature_Type
}

func (x *Tile_Feature) GetGeometry() []uint32 {
	if x != nil {
		return x.Geometry
	}
	return nil
}

// Layers are described in section 4.1 of the specification
type Tile_Layer struct {
	state protoimpl.MessageState `protogen:"open.v1"`
	// Any compliant implementation must first read the version
	// number encoded in this message and choose the correct
	// implementation for this version number before proceeding to
	// decode other parts of this message.
	Version *uint32 `protobuf:"varint,15,req,name=version,def=1" json:"version,omitempty"`
	Name    *string `protobuf:"bytes,1,req,name=name" json:"name,omitempty"`
	// The actual features in this tile.
	Features []*Tile_Feature `protobuf:"bytes,2,rep,name=features" json:"features,omitempty"`
	// Dictionary encoding for keys
	Keys []string `protobuf:"bytes,3,rep,name=keys" json:"keys,omitempty"`
	// Dictionary encoding for values
	Values []*Tile_Value `protobuf:"bytes,4,rep,name=values" json:"values,omitempty"`
	// Although this is an "optional" field it is required by the specification.
	// See https://github.com/mapbox/vector-tile-spec/issues/47
	Extent          *uint32 `protobuf:"varint,5,opt,name=extent,def=4096" json:"extent,omitempty"`
	extensionFields protoimpl.ExtensionFields
	unknownFields   protoimpl.UnknownFields
	sizeCache       protoimpl.SizeCache
}

// Default values for Tile_Layer fields.
const (
	Default_Tile_Layer_Version = uint32(1)
	Default_Tile_Layer_Extent  = uint32(4096)
)

func (x *Tile_Layer) Reset() {
	*x = Tile_Layer{}
	mi := &file_vector_tile_proto_msgTypes[3]
	ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
	ms.StoreMessageInfo(mi)
}

func (x *Tile_Layer) String() string {
	return protoimpl.X.MessageStringOf(x)
}

func (*Tile_Layer) ProtoMessage() {}

func (x *Tile_Layer) ProtoReflect() protoreflect.Message {
	mi := &file_vector_tile_proto_msgTypes[3]
	if x != nil {
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		if ms.LoadMessageInfo() == nil {
			ms.StoreMessageInfo(mi)
		}
		return ms
	}
	return mi.MessageOf(x)
}

// Deprecated: Use Tile_Layer.ProtoReflect.Descriptor instead.
func (*Tile_Layer) Descriptor() ([]byte, []int) {
	return file_vector_tile_proto_rawDescGZIP(), []int{0, 2}
}

func (x *Tile_Layer) GetVersion() uint32 {
	if x != nil && x.Version != nil {
		return *x.Version
	}
	return Default_Tile_Layer_Version
}

func (x *Tile_Layer) GetName() string {
	if x != nil && x.Name != nil {
		return *x.Name
	}
	return ""
}

func (x *Tile_Layer) GetFeatures() []*Tile_Feature {
	if x != nil {
		return x.Features
	}
	return nil
}

func (x *Tile_Layer) GetKeys() []string {
	if x != nil {
		return x.Keys
	}
	return nil
}

func (x *Tile_Layer) GetValues() []*Tile_Value {
	if x != nil {
		return x.Values
	}
	return nil
}

func (x *Tile_Layer) GetExtent() uint32 {
	if x != nil && x.Extent != nil {
		return *x.Extent
	}
	return Default_Tile_Layer_Extent
}

var File_vector_tile_proto protoreflect.FileDescriptor

const file_vector_tile_proto_rawDesc = "" +
	"\n" +
	"\x11vector_tile.proto\x12\x06protos\"\xcf\x05\n" +
	"\x04Tile\x12*\n" +
	"\x06layers\x18\x03 \x03(\v2\x12.protos.Tile.LayerR\x06layers\x1a\xf2\x01\n" +
	"\x05Value\x12!\n" +
	"\fstring_value\x18\x01 \x01(\tR\vstringValue\x12\x1f\n" +
	"\vfloat_value\x18\x02 \x01(\x02R\n" +
	"floatValue\x12!\n" +
	"\fdouble_value\x18\x03 \x01(\x01R\vdoubleValue\x12\x1b\n" +
	"\tint_value\x18\x04 \x01(\x03R\bintValue\x12\x1d\n" +
	"\n" +
	"uint_value\x18\x05 \x01(\x04R\tuintValue\x12\x1d\n" +
	"\n" +
	"sint_value\x18\x06 \x01(\x12R\tsintValue\x12\x1d\n" +
	"\n" +
	"bool_value\x18\a \x01(\bR\tboolValue*\b\b\b\x10\x80\x80\x80\x80\x02\x1a\x88\x01\n" +
	"\aFeature\x12\x11\n" +
	"\x02id\x18\x01 \x01(\x04:\x010R\x02id\x12\x16\n" +
	"\x04tags\x18\x02 \x03(\rB\x02\x10\x01R\x04tags\x122\n" +
	"\x04type\x18\x03 \x01(\x0e2\x15.protos.Tile.GeomType:\aUNKNOWNR\x04type\x12\x1e\n" +
	"\bgeometry\x18\x04 \x03(\rB\x02\x10\x01R\bgeometry\x1a\xd2\x01\n" +
	"\x05Layer\x12\x1b\n" +
	"\aversion\x18\x0f \x02(\r:\x011R\aversion\x12\x12\n" +
	"\x04name\x18\x01 \x02(\tR\x04name\x120\n" +
	"\bfeatures\x18\x02 \x03(\v2\x14.protos.Tile.FeatureR\bfeatures\x12\x12\n" +
	"\x04keys\x18\x03 \x03(\tR\x04keys\x12*\n" +
	"\x06values\x18\x04 \x03(\v2\x12.protos.Tile.ValueR\x06values\x12\x1c\n" +
	"\x06extent\x18\x05 \x01(\r:\x044096R\x06extent*\b\b\x10\x10\x80\x80\x80\x80\x02\"?\n" +
	"\bGeomType\x12\v\n" +
	"\aUNKNOWN\x10\x00\x12\t\n" +
	"\x05POINT\x10\x01\x12\x0e\n" +
	"\n" +
	"LINESTRING\x10\x02\x12\v\n" +
	"\aPOLYGON\x10\x03*\x05\b\x10\x10\x80@B\fH\x03Z\b.;protos"

var (
	file_vector_tile_proto_rawDescOnce sync.Once
	file_vector_tile_proto_rawDescData []byte
)

func file_vector_tile_proto_rawDescGZIP() []byte {
	file_vector_tile_proto_rawDescOnce.Do(func() {
		file_vector_tile_proto_rawDescData = protoimpl.X.CompressGZIP(unsafe.Slice(unsafe.StringData(file_vector_tile_proto_rawDesc), len(file_vector_tile_proto_rawDesc)))
	})
	return file_vector_tile_proto_rawDescData
}

var file_vector_tile_proto_enumTypes = make([]protoimpl.EnumInfo, 1)
var file_vector_tile_proto_msgTypes = make([]protoimpl.MessageInfo, 4)
var file_vector_tile_proto_goTypes = []any{
	(Tile_GeomType)(0),   // 0: protos.Tile.GeomType
	(*Tile)(nil),         // 1: protos.Tile
	(*Tile_Value)(nil),   // 2: protos.Tile.Value
	(*Tile_Feature)(nil), // 3: protos.Tile.Feature
	(*Tile_Layer)(nil),   // 4: protos.Tile.Layer
}
var file_vector_tile_proto_depIdxs = []int32{
	4, // 0: protos.Tile.layers:type_name -> protos.Tile.Layer
	0, // 1: protos.Tile.Feature.type:type_name -> protos.Tile.GeomType
	3, // 2: protos.Tile.Layer.features:type_name -> protos.Tile.Feature
	2, // 3: protos.Tile.Layer.values:type_name -> protos.Tile.Value
	4, // [4:4] is the sub-list for method output_type
	4, // [4:4] is the sub-list for method input_type
	4, // [4:4] is the sub-list for extension type_name
	4, // [4:4] is the sub-list for extension extendee
	0, // [0:4] is the sub-list for field type_name
}

func init() { file_vector_tile_proto_init() }
func file_vector_tile_proto_init() {
	if File_vector_tile_proto != nil {
		return
	}
	type x struct{}
	out := protoimpl.TypeBuilder{
		File: protoimpl.DescBuilder{
			GoPackagePath: reflect.TypeOf(x{}).PkgPath(),
			RawDescriptor: unsafe.Slice(unsafe.StringData(file_vector_tile_proto_rawDesc), len(file_vector_tile_proto_rawDesc)),
			NumEnums:      1,
			NumMessages:   4,
			NumExtensions: 0,
			NumServices:   0,
		},
		GoTypes:           file_vector_tile_proto_goTypes,
		DependencyIndexes: file_vector_tile_proto_depIdxs,
		EnumInfos:         file_vector_tile_proto_enumTypes,
		MessageInfos:      file_vector_tile_proto_msgTypes,
	}.Build()
	File_vector_tile_proto = out.File
	file_vector_tile_proto_goTypes = nil
	file_vector_tile_proto_depIdxs = nil
}

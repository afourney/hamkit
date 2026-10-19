// SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
//
// SPDX-License-Identifier: MIT

// Command fapsnapshot records go-aprs-fap's output for the case vectors' fap
// field (see tests/cases/README.md). It reads JSONL requests
// {"id","hex","ax25","accept_broken_mice","raw_timestamp"} on stdin and writes
// {"id","fap"} lines. Build: go build -o fapsnapshot . (Go 1.26 or later).
package main

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"time"

	fap "github.com/hessu/go-aprs-fap"
)

type input struct {
	ID               string `json:"id"`
	Hex              string `json:"hex"`
	AX25             bool   `json:"ax25"`
	AcceptBrokenMicE bool   `json:"accept_broken_mice"`
	RawTimestamp     bool   `json:"raw_timestamp"`
}

// latin1 maps each byte to one rune, matching the corpus byte carrier.
func latin1(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		b.WriteRune(rune(s[i]))
	}
	return b.String()
}

var timeType = reflect.TypeOf(time.Time{})

func plain(v reflect.Value) any {
	switch v.Kind() {
	case reflect.Pointer, reflect.Interface:
		if v.IsNil() {
			return nil
		}
		return plain(v.Elem())
	case reflect.String:
		return latin1(v.String())
	case reflect.Uint8:
		if v.Uint() == 0 {
			return nil
		}
		return latin1(string([]byte{byte(v.Uint())}))
	case reflect.Slice:
		if v.IsNil() {
			return nil
		}
		out := make([]any, v.Len())
		for i := range out {
			out[i] = plain(v.Index(i))
		}
		return out
	case reflect.Map:
		if v.IsNil() {
			return nil
		}
		out := map[string]any{}
		for _, k := range v.MapKeys() {
			out[latin1(k.String())] = plain(v.MapIndex(k))
		}
		return out
	case reflect.Struct:
		out := orderedMap{}
		t := v.Type()
		for i := 0; i < t.NumField(); i++ {
			f := t.Field(i)
			if !f.IsExported() || f.Type == timeType || (f.Type.Kind() == reflect.Pointer && f.Type.Elem() == timeType) {
				continue
			}
			out = append(out, kv{f.Name, plain(v.Field(i))})
		}
		return out
	default:
		return v.Interface()
	}
}

type kv struct {
	k string
	v any
}
type orderedMap []kv

func (m orderedMap) MarshalJSON() ([]byte, error) {
	var b strings.Builder
	b.WriteByte('{')
	for i, e := range m {
		if i > 0 {
			b.WriteByte(',')
		}
		k, _ := json.Marshal(e.k)
		v, err := json.Marshal(e.v)
		if err != nil {
			return nil, err
		}
		b.Write(k)
		b.WriteByte(':')
		b.Write(v)
	}
	b.WriteByte('}')
	return []byte(b.String()), nil
}

var skip = map[string]bool{"OrigPacket": true, "Header": true, "Body": true, "SrcCallsign": true, "DstCallsign": true, "Digipeaters": true}

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1<<24), 1<<24)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	enc := json.NewEncoder(out)
	enc.SetEscapeHTML(false)
	for in.Scan() {
		var req input
		if err := json.Unmarshal(in.Bytes(), &req); err != nil {
			panic(err)
		}
		raw, err := hex.DecodeString(req.Hex)
		if err != nil {
			panic(err)
		}
		var opts []fap.Option
		if req.AX25 {
			opts = append(opts, fap.WithAX25())
		}
		if req.AcceptBrokenMicE {
			opts = append(opts, fap.WithAcceptBrokenMicE())
		}
		if req.RawTimestamp {
			opts = append(opts, fap.WithRawTimestamp())
		}
		result := orderedMap{}
		func() {
			defer func() {
				if r := recover(); r != nil {
					result = append(result, kv{"panic", latin1(strings.TrimSpace(func() string { b, _ := json.Marshal(r); return string(b) }()))})
				}
			}()
			p, perr := fap.Parse(string(raw), opts...)
			if p != nil {
				var digis []any
				for _, d := range p.Digipeaters {
					digis = append(digis, orderedMap{{"Call", latin1(d.Call)}, {"WasDigied", d.WasDigied}})
				}
				result = append(result, kv{"header", orderedMap{{"source", latin1(p.SrcCallsign)}, {"destination", latin1(p.DstCallsign)}, {"digipeaters", digis}}})
				fields := orderedMap{}
				for _, e := range plain(reflect.ValueOf(*p)).(orderedMap) {
					if !skip[e.k] {
						fields = append(fields, e)
					}
				}
				// Only an NMEA timestamp is computed from the packet alone (RMC
				// carries a date); others are completed from the wall clock.
				if p.Format == fap.FormatNMEA && p.Timestamp != nil {
					fields = append(fields, kv{"Timestamp", p.Timestamp.UTC().Format(time.RFC3339)})
				}
				result = append(result, kv{"fields", fields})
			}
			if perr != nil {
				result = append(result, kv{"error", latin1(perr.Error())})
			}
		}()
		if err := enc.Encode(orderedMap{{"id", req.ID}, {"fap", result}}); err != nil {
			panic(err)
		}
	}
	if err := in.Err(); err != nil {
		panic(err)
	}
}

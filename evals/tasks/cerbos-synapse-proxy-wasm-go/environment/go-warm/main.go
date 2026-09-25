// Warm-up module: compiling it caches the dependencies an extension typically uses.
package main

import (
	"github.com/extism/go-pdk"
	"github.com/tidwall/gjson"
	"github.com/tidwall/sjson"
)

//go:wasmexport warm
func warm() int32 {
	out, _ := sjson.SetBytes(pdk.Input(), "warm", gjson.GetBytes(pdk.Input(), "warm").Bool())
	pdk.Output(out)
	return 0
}

func main() {}

package astravcs

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRepositories(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer t" {
			t.Fatal("auth")
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"repositories":["r"]}`))
	}))
	defer s.Close()
	v, e := New(s.URL, "t").Repositories()
	if e != nil || len(v) != 1 || v[0] != "r" {
		t.Fatalf("%v %v", v, e)
	}
}

func TestAgentJob(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Method == "POST" {
			w.Write([]byte(`{"id":"j"}`))
			return
		}
		w.Write([]byte(`{"job":{"id":"j","repo":"r","input_revision":"x","task":"t","status":"queued","result":null}}`))
	}))
	defer s.Close()
	c := New(s.URL, "t")
	id, e := c.CreateAgentJob("r", "x", "t")
	if e != nil || id != "j" {
		t.Fatalf("%s %v", id, e)
	}
	j, e := c.AgentJob("j")
	if e != nil || j.Status != "queued" {
		t.Fatalf("%v %v", j, e)
	}
}

func TestIssues(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Method == "POST" {
			w.Write([]byte(`{"id":3}`))
			return
		}
		w.Write([]byte(`{"issues":[{"id":3,"repo":"r","title":"bug","body":"","state":"open","created_by":"u"}]}`))
	}))
	defer s.Close()
	c := New(s.URL, "t")
	id, e := c.CreateIssue("r", "bug", "")
	if e != nil || id != 3 {
		t.Fatalf("%d %v", id, e)
	}
	issues, e := c.Issues("r", "open")
	if e != nil || len(issues) != 1 || issues[0].Title != "bug" {
		t.Fatalf("%v %v", issues, e)
	}
}

func TestCapabilities(t *testing.T) {
 s:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){w.Header().Set("Content-Type","application/json");w.Write([]byte(`{"product_version":"0.31.0","api_versions":[1],"repository_formats":[1],"bundle_formats":[1,2],"semantic_schemas":[0,1],"sync_protocol_versions":[1]}`))}));defer s.Close()
 c,e:=New(s.URL,"t").Capabilities();if e!=nil||c.ProductVersion!="0.31.0"||len(c.BundleFormats)!=2||c.SyncProtocolVersions[0]!=1{t.Fatalf("%v %v",c,e)}
}

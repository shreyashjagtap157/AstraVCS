package astravcs
import("net/http";"net/http/httptest";"testing")
func TestRepositories(t *testing.T){s:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){if r.Header.Get("Authorization")!="Bearer t"{t.Fatal("auth")};w.Header().Set("Content-Type","application/json");w.Write([]byte(`{"repositories":["r"]}`))}));defer s.Close();v,e:=New(s.URL,"t").Repositories();if e!=nil||len(v)!=1||v[0]!="r"{t.Fatalf("%v %v",v,e)}}

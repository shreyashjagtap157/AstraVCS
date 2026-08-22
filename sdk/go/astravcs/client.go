package astravcs
import("bytes";"encoding/json";"fmt";"io";"net/http";"strings")
type Client struct{BaseURL,Token string;HTTP *http.Client}
func New(base,token string)*Client{return &Client{strings.TrimRight(base,"/"),token,http.DefaultClient}}
func(c *Client)do(method,path string,body any,out any)error{var r io.Reader;if body!=nil{b,e:=json.Marshal(body);if e!=nil{return e};r=bytes.NewReader(b)};req,e:=http.NewRequest(method,c.BaseURL+path,r);if e!=nil{return e};req.Header.Set("Authorization","Bearer "+c.Token);req.Header.Set("Accept","application/json");if body!=nil{req.Header.Set("Content-Type","application/json")};resp,e:=c.HTTP.Do(req);if e!=nil{return e};defer resp.Body.Close();if resp.StatusCode/100!=2{b,_:=io.ReadAll(io.LimitReader(resp.Body,1<<20));return fmt.Errorf("AstraVCS HTTP %d: %s",resp.StatusCode,string(b))};return json.NewDecoder(resp.Body).Decode(out)}
func(c *Client)Repositories()([]string,error){var x struct{Repositories []string `json:"repositories"`};e:=c.do("GET","/v1/repos",nil,&x);return x.Repositories,e}

package astravcs

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

type Client struct {
	BaseURL, Token string
	HTTP           *http.Client
}

func New(base, token string) *Client {
	return &Client{strings.TrimRight(base, "/"), token, http.DefaultClient}
}
func (c *Client) do(method, path string, body any, out any) error {
	var r io.Reader
	if body != nil {
		b, e := json.Marshal(body)
		if e != nil {
			return e
		}
		r = bytes.NewReader(b)
	}
	req, e := http.NewRequest(method, c.BaseURL+path, r)
	if e != nil {
		return e
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, e := c.HTTP.Do(req)
	if e != nil {
		return e
	}
	defer resp.Body.Close()
	if resp.StatusCode/100 != 2 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		return fmt.Errorf("AstraVCS HTTP %d: %s", resp.StatusCode, string(b))
	}
	return json.NewDecoder(resp.Body).Decode(out)
}
type CompatibilityDescriptor struct {
	ProductVersion string `json:"product_version"`
	APIVersions []int `json:"api_versions"`
	RepositoryFormats []int `json:"repository_formats"`
	BundleFormats []int `json:"bundle_formats"`
	SemanticSchemas []int `json:"semantic_schemas"`
	SyncProtocolVersions []int `json:"sync_protocol_versions"`
}
func (c *Client) Capabilities() (CompatibilityDescriptor,error) {
	var x CompatibilityDescriptor
	e:=c.do("GET","/v1/capabilities",nil,&x)
	return x,e
}
func (c *Client) Repositories() ([]string, error) {
	var x struct {
		Repositories []string `json:"repositories"`
	}
	e := c.do("GET", "/v1/repos", nil, &x)
	return x.Repositories, e
}

type Organization struct { ID string `json:"id"`; Name string `json:"name"` }
type OrganizationMember struct { Principal string `json:"principal"`; Role string `json:"role"` }
func (c *Client) Organizations() ([]Organization,error) { var x struct{Organizations []Organization `json:"organizations"`};e:=c.do("GET","/v1/orgs",nil,&x);return x.Organizations,e }
func (c *Client) CreateOrganization(name string) (Organization,error) { var x Organization;e:=c.do("POST","/v1/orgs",map[string]string{"name":name},&x);return x,e }
func (c *Client) AddOrganizationMember(org,principal,role string) error { var x map[string]any;return c.do("POST","/v1/orgs/"+org+"/members",map[string]string{"principal":principal,"role":role},&x) }
func (c *Client) BindRepositoryOrganization(repo,org,visibility string) error { var x map[string]any;return c.do("POST","/v1/repos/"+repo+"/organization",map[string]string{"org":org,"visibility":visibility},&x) }

type AgentJob struct {
	ID            string  `json:"id"`
	Repo          string  `json:"repo"`
	InputRevision string  `json:"input_revision"`
	Task          string  `json:"task"`
	TargetRef     string  `json:"target_ref"`
	Status        string  `json:"status"`
	Result        *string `json:"result"`
}

func (c *Client) CreateAgentJob(repo, inputRevision, task string) (string, error) { return c.CreateAgentJobForRef(repo,inputRevision,task,"refs/heads/main") }
func (c *Client) CreateAgentJobForRef(repo, inputRevision, task, targetRef string) (string, error) {
	var x struct { ID string `json:"id"` }
	e := c.do("POST", "/v1/repos/"+repo+"/agents", map[string]any{"input_revision": inputRevision, "task": task, "capabilities": []string{"changes.create", "proposals.create"}, "network_policy": "deny", "max_seconds": 900, "target_ref": targetRef}, &x)
	return x.ID, e
}
func (c *Client) AgentJob(id string) (AgentJob, error) {
	var x struct {
		Job AgentJob `json:"job"`
	}
	e := c.do("GET", "/v1/agents/"+id, nil, &x)
	return x.Job, e
}

type Issue struct {
	ID        int    `json:"id"`
	Repo      string `json:"repo"`
	Title     string `json:"title"`
	Body      string `json:"body"`
	State     string `json:"state"`
	CreatedBy string `json:"created_by"`
}

func (c *Client) Issues(repo, state string) ([]Issue, error) {
	var x struct {
		Issues []Issue `json:"issues"`
	}
	e := c.do("GET", "/v1/repos/"+repo+"/issues?state="+state, nil, &x)
	return x.Issues, e
}
func (c *Client) CreateIssue(repo, title, body string) (int, error) {
	var x struct {
		ID int `json:"id"`
	}
	e := c.do("POST", "/v1/repos/"+repo+"/issues", map[string]string{"title": title, "body": body}, &x)
	return x.ID, e
}
func (c *Client) CommentIssue(repo string, id int, body string) (int, error) {
	var x struct {
		ID int `json:"id"`
	}
	e := c.do("POST", fmt.Sprintf("/v1/repos/%s/issues/%d/comments", repo, id), map[string]string{"body": body}, &x)
	return x.ID, e
}

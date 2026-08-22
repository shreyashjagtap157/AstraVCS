using System.Net.Http.Headers;
namespace AstraVCS;
public sealed class AstraClient(HttpClient http, string baseUrl, string token) {
  public async Task<string> GetAsync(string path, CancellationToken ct=default) { using var req=new HttpRequestMessage(HttpMethod.Get, baseUrl.TrimEnd('/')+path); req.Headers.Authorization=new AuthenticationHeaderValue("Bearer",token); using var res=await http.SendAsync(req,ct); var body=await res.Content.ReadAsStringAsync(ct); if(!res.IsSuccessStatusCode) throw new HttpRequestException($"AstraVCS HTTP {(int)res.StatusCode}: {body}"); return body; }
}

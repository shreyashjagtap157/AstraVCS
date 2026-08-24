package dev.astravcs;
import java.net.URI;import java.net.http.*;import java.io.IOException;
public final class AstraClient { private final String base,token; private final HttpClient http;
 public AstraClient(String base,String token){this.base=base.replaceAll("/+$","");this.token=token;this.http=HttpClient.newHttpClient();}
 public String get(String path)throws IOException,InterruptedException{var req=HttpRequest.newBuilder(URI.create(base+path)).header("Authorization","Bearer "+token).header("Accept","application/json").GET().build();var r=http.send(req,HttpResponse.BodyHandlers.ofString());if(r.statusCode()/100!=2)throw new IOException("AstraVCS HTTP "+r.statusCode()+": "+r.body());return r.body();}
 public String post(String path,String json)throws IOException,InterruptedException{var req=HttpRequest.newBuilder(URI.create(base+path)).header("Authorization","Bearer "+token).header("Accept","application/json").header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(json)).build();var r=http.send(req,HttpResponse.BodyHandlers.ofString());if(r.statusCode()/100!=2)throw new IOException("AstraVCS HTTP "+r.statusCode()+": "+r.body());return r.body();}
 public String capabilities()throws IOException,InterruptedException{return get("/v1/capabilities");}
 public String agentJob(String id)throws IOException,InterruptedException{return get("/v1/agents/"+id);}
}

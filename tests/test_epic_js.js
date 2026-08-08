const assert = require('assert');
const E = require('../tracepic/htdocs/epic.js');

// Fixtures: id, priority_value ('1' blocker .. '6'), summary, changetime, status
const links = [
  {id:1, summary:'zebra',  priority_value:'3', changetime:100, status:'new'},
  {id:2, summary:'apple',  priority_value:'1', changetime:300, status:'closed'},
  {id:3, summary:'mango',  priority_value:'6', changetime:200, status:'new'},
  {id:4, summary:'banana', priority_value:'1', changetime:400, status:'new'}, // tie prio with #2
  {id:5, summary:'kiwi',   priority_value:'',  changetime:50,  status:'new'}, // no priority
];

function ids(list){ return list.map(x=>x.id); }

// 1) priority desc = most severe (value 1) first; ties by id asc; empty last
let r = E.sortedLinks(links,'priority','desc');
assert.deepStrictEqual(ids(r), [2,4,1,3,5], 'priority desc: '+ids(r));

// 2) priority asc = least severe first (empty treated as least severe -> first)
r = E.sortedLinks(links,'priority','asc');
assert.deepStrictEqual(ids(r), [5,3,1,4,2], 'priority asc: '+ids(r));

// 3) summary asc alphabetical
r = E.sortedLinks(links,'summary','asc');
assert.deepStrictEqual(ids(r), [2,4,5,3,1], 'summary asc: '+ids(r));

// 4) summary desc reverse
r = E.sortedLinks(links,'summary','desc');
assert.deepStrictEqual(ids(r), [1,3,5,4,2], 'summary desc: '+ids(r));

// 5) id desc
r = E.sortedLinks(links,'id','desc');
assert.deepStrictEqual(ids(r), [5,4,3,2,1], 'id desc');

// 6) modified (changetime) desc = newest first
r = E.sortedLinks(links,'modified','desc');
assert.deepStrictEqual(ids(r), [4,2,3,1,5], 'modified desc: '+ids(r));

// 7) modified asc = oldest first
r = E.sortedLinks(links,'modified','asc');
assert.deepStrictEqual(ids(r), [5,1,3,2,4], 'modified asc: '+ids(r));

// 8) naturalOrder defaults
assert.strictEqual(E.naturalOrder('priority'),'desc');
assert.strictEqual(E.naturalOrder('modified'),'desc');
assert.strictEqual(E.naturalOrder('id'),'desc');
assert.strictEqual(E.naturalOrder('summary'),'asc');

// 9) prioKey
assert.strictEqual(E.prioKey({priority_value:'2'}),2);
assert.ok(E.prioKey({priority_value:''}) > 1e8);

// 10) initialState validation
let st = E.initialState({links:links, sort:{field:'bogus',order:'weird'}, page_size:'x'});
assert.strictEqual(st.field,'priority'); assert.strictEqual(st.order,'desc'); assert.strictEqual(st.pageSize,10);
st = E.initialState({links:links, sort:{field:'summary',order:'asc'}, page_size:'3'});
assert.strictEqual(st.field,'summary'); assert.strictEqual(st.order,'asc'); assert.strictEqual(st.pageSize,3);

// 11) pagination slicing behaviour (mirror render(): sort then slice)
function page(list, field, order, pageSize, pageNum){
  const s = E.sortedLinks(list, field, order);
  const from = (pageNum-1)*pageSize;
  return s.slice(from, from+pageSize).map(x=>x.id);
}
assert.deepStrictEqual(page(links,'id','asc',2,1),[1,2],'page1');
assert.deepStrictEqual(page(links,'id','asc',2,2),[3,4],'page2');
assert.deepStrictEqual(page(links,'id','asc',2,3),[5],'page3 (last, partial)');
const numPages = Math.ceil(links.length/2);
assert.strictEqual(numPages,3,'numPages');

console.log('All epic.js logic tests passed ('+links.length+' fixtures).');

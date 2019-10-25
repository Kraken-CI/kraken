import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { BranchMgmtComponent } from './branch-mgmt.component';

describe('BranchMgmtComponent', () => {
  let component: BranchMgmtComponent;
  let fixture: ComponentFixture<BranchMgmtComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ BranchMgmtComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(BranchMgmtComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

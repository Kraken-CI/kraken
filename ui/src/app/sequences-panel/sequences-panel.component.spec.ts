import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SequencesPanelComponent } from './sequences-panel.component';

describe('SequencesPanelComponent', () => {
  let component: SequencesPanelComponent;
  let fixture: ComponentFixture<SequencesPanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ SequencesPanelComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SequencesPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
